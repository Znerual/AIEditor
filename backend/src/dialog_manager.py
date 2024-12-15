# backend/src/dialog_manager.py
import logging
from embedding_manager import EmbeddingManager
from models import FileContent, Document
import google.generativeai as genai
import threading
import time
from typing import List, Dict, Optional, Any
from dataclasses import dataclass
from utils import delta_to_string
from delta import Delta

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

@dataclass
class DialogTurn:
    """Stores the context of a single dialog turn"""
    user_message: str
    action_plan: str
    function_calls: List[Dict]
    response: str
    
class DebugModel:
    def generate_content(self, prompt):
        logging.debug(f"DebugModel generating content for prompt: {prompt}")
        time.sleep(1)
        return {"text" : "Debug response with simulated function calls."}

class DialogManager:
    _embedding_manager: Optional[EmbeddingManager] = None

    def __init__(self, api_key, debug=False):
        self.debug = debug
        if debug:
            self.model = DebugModel()
            logging.info("DialogManager running in debug mode.")
        else:
            genai.configure(api_key=api_key)
            self.model = genai.GenerativeModel(
                'gemini-1.5-flash',
                tools=[
                    {
                        "function_declarations": [
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
                            }
                        ]
                    }
                ]
            )
            logging.info("DialogManager initialized with Gemini 1.5 Flash model.")

        self._embedding_manager = EmbeddingManager()
        self.dialog_history: Dict[int, List[DialogTurn]] = {}  # User ID to dialog history

    def start_new_dialog(self, user_id: int):
        """Starts a new dialog for the given user"""
        self.dialog_history[user_id] = []

    def get_response(self, user_id: int, user_message: str, document_id: Optional[int] = None) -> Dict:
        """
        Generates a response to the user's message using a two-step prompting strategy.

        Args:
            user_id: The ID of the user.
            user_message: The user's message.
            document_id: The ID of the document being edited (optional).

        Returns:
            A dictionary containing the response text and suggested edits.
        """
        logging.info(f"Getting response for user {user_id}, message: {user_message}")

        # Retrieve dialog history
        history = self.dialog_history.get(user_id, [])

        # --- Step 1: Create an Action Plan ---
        action_plan_prompt = self._build_action_plan_prompt(user_message, history, document_id)
        
        if self.debug:
            action_plan_response = self.model.generate_content(action_plan_prompt)
            action_plan = action_plan_response.text
        else:
            action_plan_response = self.model.generate_content(action_plan_prompt)
            action_plan = action_plan_response.text
        logging.info(f"Generated action plan: {action_plan}")

        # --- Step 2: Generate Response with Function Calls ---
        function_call_prompt = self._build_function_call_prompt(user_message, history, document_id, action_plan)
        
        if self.debug:
             # Debug mode: Simulate function calls
            function_calls = [{"name": "insert_text", "arguments": {'text': 'inserted text', 'position': 0}}]
            response_text = "Debug response with simulated function calls."
        else:
            function_call_response = self.model.generate_content(function_call_prompt)
            
            function_calls = []
            try:
                for part in function_call_response.parts:
                    function_call = {
                        "name": part.function_call.name,
                        "arguments": {k: v for k, v in part.function_call.args.items()}
                    }
                    function_calls.append(function_call)
            except Exception as e:
                logging.error(f"Error extracting function calls: {e}")
                

            # Call functions and get the actual response
            response_text = self._execute_function_calls(document_id, function_calls)
        
        logging.info(f"Generated response: {response_text}, function calls: {function_calls}")

        # Update dialog history
        history.append(DialogTurn(user_message, action_plan, function_calls, response_text))
        self.dialog_history[user_id] = history

        return {
            "response": response_text,
            "suggested_edits": function_calls,  # Function calls represent the edit suggestions
        }

    def _build_action_plan_prompt(self, user_message: str, history: List[DialogTurn], document_id: Optional[int]) -> str:
        """Builds the prompt for generating an action plan."""
        prompt = "## Dialog History:\n"
        for turn in history:
            prompt += f"User: {turn.user_message}\n"
            prompt += f"Agent (Action Plan): {turn.action_plan}\n"  # Include previous action plan
            prompt += f"Agent (Response): {turn.response}\n" # Include previous response

        if document_id:
            try:
                document = Document.query.get(document_id)
                if document:
                    document_content = document.get_current_delta()
                    document_text = delta_to_string(document_content)
                    prompt += "\n## Document Context:\n"
                    prompt += document_text[:2048]  # Limit context size for now
            except Exception as e:
                logging.error(f"Error getting document content: {e}")

        prompt += "\n## User Message:\n"
        prompt += user_message
        prompt += "\n## Task:\nCreate a detailed action plan for responding to the user's request. Consider the dialog history and the document context. The action plan should outline the steps needed to fulfill the user's request, including any necessary insertions, deletions, or replacements in the document. DO NOT perform the actions, just describe them in the plan.\n"
        prompt += "## Action Plan:\n"
        return prompt

    def _build_function_call_prompt(self, user_message: str, history: List[DialogTurn], document_id: Optional[int], action_plan: str) -> str:
        """Builds the prompt for generating function calls."""
        prompt = "## Dialog History:\n"
        for turn in history:
            prompt += f"User: {turn.user_message}\n"
            prompt += f"Agent (Action Plan): {turn.action_plan}\n"
            prompt += f"Agent (Response): {turn.response}\n"

        if document_id:
            try:
                document = Document.query.get(document_id)
                if document:
                    document_content = document.get_current_delta()
                    document_text = delta_to_string(document_content)
                    prompt += "\n## Document Context:\n"
                    prompt += document_text[:2048]  # Limit context size for now
            except Exception as e:
                logging.error(f"Error getting document content: {e}")

        prompt += "\n## User Message:\n"
        prompt += user_message
        prompt += "\n## Action Plan:\n"
        prompt += action_plan
        prompt += "\n## Task:\nBased on the action plan, generate a response to the user. You can use the following functions to edit the document:\n"
        prompt += "- `insert_text(text: str, position: int)`: Inserts text at the specified position.\n"
        prompt += "- `delete_text(start: int, end: int)`: Deletes text between the start and end positions.\n"
        prompt += "- `replace_text(start: int, end: int, new_text: str)`: Replaces text between the start and end positions with new text.\n"
        prompt += "Return only the function calls needed to execute the action plan. DO NOT produce any other output text.\n"
        prompt += "## Agent Response (with function calls):\n"
        
        return prompt

    def _execute_function_calls(self, document_id: Optional[int], function_calls: List[Dict]) -> str:
        """Executes the function calls and returns a natural language response."""
        if not document_id:
            return "Error: No document context provided for function calls."
        
        document = Document.query.get(document_id)
        if not document:
            return "Error: Document not found."
        
        response_parts = []
        for call in function_calls:
            try:
                if call["name"] == "insert_text":
                    text = call["arguments"]["text"]
                    position = int(call["arguments"]["position"])
                    current_delta = document.get_current_delta()
                    new_delta = current_delta.compose(Delta().retain(position).insert(text))
                    document.apply_delta(new_delta.ops)
                    response_parts.append(f"Inserted '{text}' at position {position}.")

                elif call["name"] == "delete_text":
                    start = int(call["arguments"]["start"])
                    end = int(call["arguments"]["end"])
                    current_delta = document.get_current_delta()
                    new_delta = current_delta.compose(Delta().retain(start).delete(end - start))
                    document.apply_delta(new_delta.ops)

                    response_parts.append(f"Deleted text from position {start} to {end}.")

                elif call["name"] == "replace_text":
                    start = int(call["arguments"]["start"])
                    end = int(call["arguments"]["end"])
                    new_text = call["arguments"]["new_text"]
                    current_delta = document.get_current_delta()
                    new_delta = current_delta.compose(Delta().retain(start).delete(end - start).insert(new_text))
                    document.apply_delta(new_delta.ops)
                    response_parts.append(f"Replaced text from position {start} to {end} with '{new_text}'.")

                else:
                    response_parts.append(f"Error: Unknown function '{call['name']}'.")
            except (KeyError, ValueError) as e:
                response_parts.append(f"Error: Invalid function call arguments: {e}")

        from app import db
        db.session.commit()
        return " ".join(response_parts)

    def apply_edit(self, user_id: int, document_id: int, edit_id: int, accepted: bool):
      """Applies or rejects a suggested edit."""
      logging.info(f"Applying edit for user {user_id}, document {document_id}, edit {edit_id}, accepted: {accepted}")
      history = self.dialog_history.get(user_id, [])
      if not history:
          raise ValueError("No dialog history found for user.")

      # Find the edit in the history (in this case a function call)
      function_call = None
      for turn in reversed(history):  # Iterate in reverse to find the most recent
          for suggested_function_call in turn.function_calls:
              if suggested_function_call["name"] == edit_id: # Assuming the edit_id is the function name
                  function_call = suggested_function_call
                  break
          if function_call:
              break

      if not function_call:
          raise ValueError("Edit not found.")
          
      if accepted:
          # In this setup, edits are already applied, so we just update the status
          function_call["status"] = "accepted"
      else:
          function_call["status"] = "rejected"
          