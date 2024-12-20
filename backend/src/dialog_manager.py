# backend/src/dialog_manager.py
import logging
from embedding_manager import EmbeddingManager
from models import FileContent, Document, db
import google.generativeai as genai
import threading
import time
from typing import List, Dict, Optional, Any, Tuple
from dataclasses import dataclass, field
from utils import delta_to_string
from delta import Delta
import json

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class DialogTurn:
    """Stores the context of a single dialog turn"""
    user_message: str
    action_plan: str
    function_calls: List[Dict]
    response: str
    relevant_file_ids: Optional[List[int]] = None  # Store IDs of relevant files
    relevant_document_ids: Optional[List[str]] = None # Store the IDs of relevant documents

@dataclass
class FunctionCall:
    """Represents a function call with its arguments and status"""
    name: str
    arguments: Dict[str, Any]
    status: Optional[str] = None  

    def to_dict(self):
        """Converts the FunctionCall to a dictionary."""
        return {
            "name": self.name,
            "arguments": self.arguments,
            "status": self.status
        }


class DebugModel:
    def __init__(self, model_name):
        self.model_name = model_name

    def generate_content(self, prompt, tools=None, safety_settings=None, generation_config=None):
        logging.debug(f"{self.model_name} generating content for prompt: {prompt}")
        time.sleep(1)
        if self.model_name == 'gemini-1.5-pro-latest':
            # Simulate an action plan for debugging
            return DebugResponse(text=json.dumps([
                {"name": "find_text", "arguments": {"search_text": "text to replace"}},
                {"name": "replace_text", "arguments": {"start": 0, "end": 15, "new_text": "replaced text"}}
            ]))
        elif self.model_name == 'gemini-1.5-flash-latest':
             # Simulate function calls and response for debugging
            return DebugResponse(
                text="I have replaced 'text to replace' with 'replaced text'.",
                function_calls=[
                    {"name": "replace_text", "arguments": {"start": 0, "end": 15, "new_text": "replaced text"}}]
            )
        else:
            return DebugResponse(text="Debug response from unknown model.")

class DebugResponse:
    def __init__(self, text=None, function_calls=None):
        self.text = text
        self.parts = [DebugPart(function_call=call) for call in (function_calls or [])]
        self.candidates = [self]  # Simulate the structure needed for text extraction

    def __getitem__(self, key):
        if key == 'text':
            return self.text
        raise KeyError(key)

class DebugPart:
    def __init__(self, function_call=None):
        self.function_call = DebugFunctionCall(**function_call) if function_call else None

class DebugFunctionCall:
    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments
        self.args = arguments # align with gemini

class DialogManager:
    _embedding_manager: Optional[EmbeddingManager] = None

    def __init__(self, api_key, debug=False):
        self.debug = debug
        if debug:
            self.planning_model = DebugModel('gemini-1.5-pro-latest')
            self.execution_model = DebugModel('gemini-1.5-flash-latest')
            logging.info("DialogManager running in debug mode.")
        else:
            genai.configure(api_key=api_key)
            self.planning_model = genai.GenerativeModel('gemini-1.5-pro-latest')
            self.execution_model = genai.GenerativeModel(
                'gemini-1.5-flash-latest',
                safety_settings={
                    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                },
                generation_config={
                    "temperature": 0.2
                }
            )
            logging.info("DialogManager initialized with Gemini 1.5 models.")

        self._embedding_manager = EmbeddingManager()
        self.dialog_history: Dict[int, List[DialogTurn]] = {}  # User ID to dialog history
        self.function_definitions = [
            {
                "name": "insert_text",
                "description": "Inserts text at the specified position in the document.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "text": {
                            "type": "string",
                            "description": "The text to insert"
                        },
                        "position": {
                            "type": "integer",
                            "description": "The position to insert the text at (0-indexed)"
                        }
                    },
                    "required": [
                        "text",
                        "position"
                    ]
                }
            },
            {
                "name": "delete_text",
                "description": "Deletes text from the specified start to end position in the document.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "integer",
                            "description": "The start position of the text to delete (0-indexed)"
                        },
                        "end": {
                            "type": "integer",
                            "description": "The end position of the text to delete (0-indexed)"
                        }
                    },
                    "required": [
                        "start",
                        "end"
                    ]
                }
            },
            {
                "name": "replace_text",
                "description": "Replaces text between the specified start and end positions with new text.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "start": {
                            "type": "integer",
                            "description": "The start position of the text to replace (0-indexed)"
                        },
                        "end": {
                            "type": "integer",
                            "description": "The end position of the text to replace (0-indexed)"
                        },
                        "new_text": {
                            "type": "string",
                            "description": "The new text to replace with"
                        }
                    },
                    "required": [
                        "start",
                        "end",
                        "new_text"
                    ]
                }
            },
            {
                "name": "find_text",
                "description": "Finds the position of a specific text within the document.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "search_text": {
                            "type": "string",
                            "description": "The text to search for"
                        }
                    },
                    "required": ["search_text"]
                }
            }
        ]

    def start_new_dialog(self, user_id: int):
        """Starts a new dialog for the given user"""
        self.dialog_history[user_id] = []

    def get_response(self, user_id: int, user_message: str, document_id: Optional[int] = None, current_content_selection: Optional[List[Dict]] = None) -> Dict:
        """
        Generates a response to the user's message using a two-step prompting strategy.

        Args:
            user_id: The ID of the user.
            user_message: The user's message.
            document_id: The ID of the document being edited (optional).
            current_content_selection: The currently selected content items (optional).

        Returns:
            A dictionary containing the response text and suggested edits.
        """
        logging.info(f"Getting response for user {user_id}, message: {user_message}, document: {document_id}, content selection: {current_content_selection}")

        # Retrieve dialog history
        history = self.dialog_history.get(user_id, [])

        # Prepare relevant content based on selection using EmbeddingManager
        relevant_file_ids = []
        relevant_document_ids = []
        relevant_content_excerpts = []

        if current_content_selection:
            try:
                file_ids = [item['file_id'] for item in current_content_selection if item['content_type'] == 'file_content']
                doc_ids = [item['file_id'] for item in current_content_selection if item['content_type'] == 'document']
                
                file_embeddings_ids = []
                if file_ids:
                    file_contents = FileContent.query.filter(FileContent.id.in_(file_ids)).all()
                    for file_content in file_contents:
                        file_embeddings_ids.append(self._embedding_manager.get_embeddings(file_content))

                if doc_ids:
                    documents = Document.query.filter(Document.id.in_(doc_ids)).all()
                    for doc in documents:
                        file_embeddings_ids.append(self._embedding_manager.get_embeddings(doc))

                
                if file_embeddings_ids:
                    similar_sequences = self._embedding_manager._find_similar_sequences(
                        text=user_message,
                        embedding_ids=file_embeddings_ids,
                        limit=5  # Limit to top 5 relevant sequences
                    )

                    for sequence in similar_sequences:
                        if sequence.file.content_id:
                            relevant_file_ids.append(sequence.file.content_id)
                            relevant_content_excerpts.append(sequence.sequence_text)
                        elif sequence.file.document_id:
                            relevant_document_ids.append(sequence.file.document_id)
                            relevant_content_excerpts.append(sequence.sequence_text)

            except Exception as e:
                logging.error(f"Error getting relevant content embeddings: {e}")

        relevant_content = "\n\n".join(relevant_content_excerpts)

        # --- Step 1: Create an Action Plan ---
        action_plan_prompt = self._build_action_plan_prompt(user_message, history, document_id, relevant_content, relevant_file_ids, relevant_document_ids)
        
        if self.debug:
            action_plan_response = self.planning_model.generate_content(action_plan_prompt)
            action_plan = action_plan_response.text
        else:
            action_plan_response = self.planning_model.generate_content(
                action_plan_prompt, generation_config=genai.GenerationConfig(
                response_mime_type="application/json"
                ),
            )
            action_plan = action_plan_response.text
            try:
                # Attempt to parse the action plan as JSON
                action_plan = json.loads(action_plan)
            except json.JSONDecodeError:
                logging.error(f"Failed to parse action plan as JSON: {action_plan_response.text}")
                action_plan = []  # or some other default/fallback action plan
        logging.info(f"Generated action plan: {action_plan}")

        # --- Step 2: Generate Response with Function Calls ---
        function_call_prompt = self._build_function_call_prompt(user_message, history, document_id, action_plan)
        if self.debug:
            # In debug mode, simulate function calls without execution
            function_calls = [
                FunctionCall(name="insert_text", arguments={'text': 'inserted text', 'position': 4}, status="suggested")
            ]
            response_text = "Here are some suggested edits (debug mode)." 
        else:
            function_call_response = self.execution_model.generate_content(
                function_call_prompt,
                tools=[{"function_declarations": self.function_definitions}]
            )

            function_calls = []
            response_text = ""

            # Check if the response has function calls
            if function_call_response.candidates and function_call_response.candidates[0].content.parts:
                
                function_call_parts = [part for part in function_call_response.candidates[0].content.parts if part.function_call]
                
                if function_call_parts:
                    # Extract function calls
                    for part in function_call_parts:
                        function_call = part.function_call
                        function_calls.append(FunctionCall(
                            name=function_call.name,
                            arguments={k: v for k, v in function_call.args.items()},
                            status="suggested"
                        ))

                    # Instead of executing the function calls here, we will only generate a descriptive response
                    response_text = self._describe_actions(function_calls)
                else:
                    # If no function calls, use text response
                    response_text = function_call_response.text
            else:
                response_text = "No response from model."

        logging.info(f"Generated response: {response_text}, function calls: {function_calls}")

        # Update dialog history (without actually applying edits)
        # Store the suggested function calls in the dialog history
        history.append(DialogTurn(
            user_message, 
            json.dumps(action_plan), 
            function_calls, 
            response_text, 
            relevant_file_ids, 
            relevant_document_ids
        ))
        self.dialog_history[user_id] = history

        # Convert function calls to dictionaries before returning
        function_call_dicts = [fc.to_dict() for fc in function_calls]

        return {
            "response": response_text,
            "suggested_edits": function_call_dicts,
        }

    def _build_action_plan_prompt(self, user_message: str, history: List[DialogTurn], document_id: Optional[int], relevant_content: str, relevant_file_ids: List[int], relevant_document_ids: List[str]) -> str:
        """
        Builds the prompt for generating an action plan.
        Now includes relevant file content IDs in the prompt to potentially reference them.
        """
        prompt = "## Dialog History:\n"
        for turn in history:
            prompt += f"User: {turn.user_message}\n"
            prompt += f"Agent (Action Plan): {turn.action_plan}\n"
            prompt += f"Agent (Response): {turn.response}\n"
            if turn.relevant_file_ids:
                prompt += f"Relevant File IDs: {turn.relevant_file_ids}\n"
            if turn.relevant_document_ids:
                prompt += f"Relevant Document IDs: {turn.relevant_document_ids}\n"

        if document_id:
            try:
                document = Document.query.get(document_id)
                if document:
                    document_content = document.get_current_delta()
                    document_text = delta_to_string(document_content)
                    prompt += "\n## Document Context:\n"
                    prompt += document_text[:4096]
            except Exception as e:
                logging.error(f"Error getting document content: {e}")

        # Add relevant content to the prompt
        if relevant_content:
            prompt += f"\n## Relevant Content:\n{relevant_content[:4096]}\n"

        # Include relevant file and document IDs in the prompt
        if relevant_file_ids:
            prompt += f"\n## Relevant File IDs:\n{relevant_file_ids}\n"
        if relevant_document_ids:
            prompt += f"\n## Relevant Document IDs:\n{relevant_document_ids}\n"

        prompt += "\n## User Message:\n"
        prompt += user_message
        prompt += "\n## Task:\nCreate a detailed action plan for responding to the user's request and editing the document. The plan should include specific, actionable steps with exact positions and content for each edit. Consider the dialog history, the current document content, and any relevant content from other documents. Use the provided relevant file and document IDs to refer to specific content when necessary. Break down the task into the smallest possible steps. Each step must be one of these actions:\n"
        prompt += "- `insert_text(text: str, position: int)`: Insert text at a specific position.\n"
        prompt += "- `delete_text(start: int, end: int)`: Delete text between start and end positions.\n"
        prompt += "- `replace_text(start: int, end: int, new_text: str)`: Replace text between start and end with new text.\n"
        prompt += "- `find_text(search_text: str)`: Find the position of a specific text.\n"
        prompt += "Use `find_text` if you need to determine the position for other actions. Do not assume positions without prior confirmation. Always use a find action before delete or replace. When using find, store the resulting index into a variable. Use this variable as positional argument for any subsequent insert, delete or replace. You can combine `find_text` with `insert_text`, `delete_text`, or `replace_text` when necessary.\n"
        prompt += "Output the action plan as a JSON array of actions, where each action corresponds to one of the specified functions. Do not perform the actions, only describe them in the plan.\n"
        prompt += "## Action Plan:\n"
        return prompt

    def _build_function_call_prompt(self, user_message: str, history: List[DialogTurn], document_id: Optional[int], action_plan: str) -> str:
        """Builds the prompt for generating function calls."""
        prompt = "## Dialog History:\n"
        for turn in history:
            prompt += f"User: {turn.user_message}\n"
            prompt += f"Agent (Action Plan): {turn.action_plan}\n"
            prompt += f"Agent (Response): {turn.response}\n"
            if turn.relevant_file_ids:
                prompt += f"Relevant File IDs: {turn.relevant_file_ids}\n"
            if turn.relevant_document_ids:
                prompt += f"Relevant Document IDs: {turn.relevant_document_ids}\n"

        if document_id:
            try:
                document = Document.query.get(document_id)
                if document:
                    document_content = document.get_current_delta()
                    document_text = delta_to_string(document_content)
                    prompt += "\n## Document Context:\n"
                    prompt += document_text[:4096]
            except Exception as e:
                logging.error(f"Error getting document content: {e}")

        prompt += "\n## User Message:\n"
        prompt += user_message
        prompt += "\n## Action Plan:\n"
        prompt += str(action_plan)  # Ensure action_plan is treated as a string
        prompt += "\n## Task:\nExecute the actions from the action plan. You can use the following functions to edit the document. Refer to specific content from relevant files and documents using their IDs when necessary:\n"
        for func_def in self.function_definitions:
            prompt += f"- `{func_def['name']}`: {func_def['description']}\n"
            if 'parameters' in func_def and 'properties' in func_def['parameters']:
                for param_name, param_details in func_def['parameters']['properties'].items():
                    prompt += f"  - `{param_name}` ({param_details.get('type', 'unknown')}): {param_details.get('description', '')}\n"

        prompt += "Return a response confirming the execution of each action. Use only the specified functions to interact with the document. For each function called return a user readable summary of what you did. Do this in a verbose, step by step manner. If the action plan does not require any function calls, respond naturally.\n"
        prompt += "## Agent Response:\n"
        return prompt

    def _execute_function_calls(self, document_id: Optional[int], function_calls: List[FunctionCall]) -> Tuple[str, List[Delta]]:
        """Executes the function calls and returns a natural language response."""
        if not document_id:
            return "Error: No document context provided for function calls.", []

        document = Document.query.get(document_id)
        if not document:
            return "Error: Document not found.", []

        document_content = document.get_current_delta()
        document_text = delta_to_string(document_content)

        response_parts = []
        deltas = []
        for call in function_calls:
            try:
                if call.name == "insert_text":
                    text = call.arguments["text"]
                    position = int(call.arguments["position"])
                    current_delta = document.get_current_delta()
                    new_delta = current_delta.compose(Delta().retain(position).insert(text))
                    deltas.append(new_delta.ops)
                    document.apply_delta(new_delta.ops)
                    response_parts.append(f"Inserted '{text}' at position {position}.")
                    call.status = "success"  # Update status

                elif call.name == "delete_text":
                    start = int(call.arguments["start"])
                    end = int(call.arguments["end"])
                    current_delta = document.get_current_delta()
                    new_delta = current_delta.compose(Delta().retain(start).delete(end - start))
                    deltas.append(new_delta.ops)
                    document.apply_delta(new_delta.ops)
                    response_parts.append(f"Deleted text from position {start} to {end}.")
                    call.status = "success"  # Update status

                elif call.name == "replace_text":
                    start = int(call.arguments["start"])
                    end = int(call.arguments["end"])
                    new_text = call.arguments["new_text"]
                    current_delta = document.get_current_delta()
                    new_delta = current_delta.compose(Delta().retain(start).delete(end - start).insert(new_text))
                    deltas.append(new_delta.ops)
                    document.apply_delta(new_delta.ops)
                    response_parts.append(f"Replaced text from position {start} to {end} with '{new_text}'.")
                    call.status = "success"  # Update status

                elif call.name == "find_text":
                    search_text = call.arguments["search_text"]
                    position = document_text.find(search_text)
                    if position != -1:
                        response_parts.append(
                            f"Found the text '{search_text}' at position {position}."
                        )
                    else:
                        response_parts.append(
                            f"Could not find the text '{search_text}' in the document."
                        )
                    call.status = "success"  # Update status

                else:
                    response_parts.append(f"Error: Unknown function '{call.name}'.")
                    call.status = "failed"

            except (KeyError, ValueError) as e:
                response_parts.append(f"Error: Invalid function call arguments: {e}")
                call.status = "failed"

        db.session.commit()
        return " ".join(response_parts), deltas
    
    def _describe_actions(self, function_calls: List[FunctionCall]) -> str:
        """
        Generates a natural language description of the suggested actions without executing them.
        """
        if not function_calls:
            return "No specific actions suggested."

        descriptions = []
        for call in function_calls:
            try:
                if call.name == "insert_text":
                    text = call.arguments["text"]
                    position = int(call.arguments["position"])
                    descriptions.append(f"I suggest inserting the text '{text}' at position {position}.")

                elif call.name == "delete_text":
                    start = int(call.arguments["start"])
                    end = int(call.arguments["end"])
                    descriptions.append(f"I suggest deleting the text between positions {start} and {end}.")

                elif call.name == "replace_text":
                    start = int(call.arguments["start"])
                    end = int(call.arguments["end"])
                    new_text = call.arguments["new_text"]
                    descriptions.append(f"I suggest replacing the text between positions {start} and {end} with '{new_text}'.")

                elif call.name == "find_text":
                    search_text = call.arguments["search_text"]
                    descriptions.append(f"I will first find the position of the text '{search_text}'.")

                else:
                    descriptions.append(f"Error: Unknown function '{call.name}'.")

            except (KeyError, ValueError) as e:
                descriptions.append(f"Error: Invalid function call arguments: {e}")

        return " ".join(descriptions)

    def apply_edit(self, user_id: int, document_id: int, edit_id: str, accepted: bool):
        """Applies or rejects a suggested edit."""
        logging.info(f"Applying edit for user {user_id}, document {document_id}, edit {edit_id}, accepted: {accepted}")
        history = self.dialog_history.get(user_id, [])
        if not history:
            raise ValueError("No dialog history found for user.")

        # Find the edit in the history (in this case a function call)
        function_call_index = None
        turn_index = None
        for i, turn in enumerate(reversed(history)):
            for j, suggested_function_call in enumerate(turn.function_calls):
                if suggested_function_call.name == edit_id:
                    function_call_index = j
                    turn_index = len(history) - 1 - i
                    break
            if function_call_index is not None:
                break

        if function_call_index is None:
            raise ValueError("Edit not found.")

        # Access the function call using the found indices
        function_call = history[turn_index].function_calls[function_call_index]

        response = ""
        deltas = []

        if accepted:
            # Apply the function call
            response, deltas = self._execute_function_calls(document_id, [function_call])  # Pass a list with a single function call
            function_call.status = "accepted"
            logging.info(f"Function call {function_call.name} executed: {response}")
        else:
            function_call.status = "rejected"
            logging.info(f"Function call {function_call.name} rejected.")

        # Update the dialog history
        self.dialog_history[user_id] = history

        return response, deltas