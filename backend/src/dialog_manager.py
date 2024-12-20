# backend/src/dialog_manager.py
import logging
from document_manager import DocumentManager
from embedding_manager import EmbeddingManager
from models import FileContent, Document
import google.generativeai as genai
import time
from typing import List, Dict, Optional, Any, Tuple, Union
from dataclasses import dataclass, field
from delta import Delta
import json
import enum
import typing_extensions as typing
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import re
import uuid

logger = logging.getLogger('eddy_logger')

    
class ActionType(enum.Enum):
    INSERT_TEXT = "insert_text"
    DELETE_TEXT = "delete_text"
    REPLACE_TEXT = "replace_text"
    FIND_TEXT = "find_text"

@dataclass
class FunctionCall:
    """Represents a function call with its arguments and status"""
    action_type: ActionType
    arguments: Dict[str, Any]
    status: Optional[str] = None

    def __post_init__(self):
        self.id = uuid.uuid4()

    def to_dict(self):
        """Converts the FunctionCall to a dictionary."""
        return {
            "id": self.id,
            "name": self.action_type,
            "arguments": self.arguments,
            "status": self.status
        }
    def _get_param_str(self):
        return ", ".join([f"{key}={value}" for key, value in self.arguments.items()])
    
    def __str__(self):
        if self.action_type == ActionType.INSERT_TEXT:
            return f"{self.status} insert_text({self._get_param_str()})"
        elif self.action_type == ActionType.DELETE_TEXT:
            return f"{self.status} delete_text({self._get_param_str()})"
        elif self.action_type == ActionType.REPLACE_TEXT:
            return f"{self.status} replace_text({self._get_param_str()})"
        elif self.action_type == ActionType.FIND_TEXT:
            return f"{self.status} find_text({self._get_param_str()})"
        else:
            return f"Unknown action type: {self.action_type}"

class Decision(enum.Enum):
    APPLY = "apply"
    REJECT = "reject"

class Action(typing.TypedDict):
    action_type: ActionType
    action_input_start_variable_name : str
    action_input_end_variable_name : str
    action_text_input: str
    find_action_start_variable_name: str
    find_action_end_variable_name: str
    action_explanation: str

class Evaluation(typing.TypedDict):
    decision: Decision
    explanation: str

@dataclass
class DialogTurn:
    """Stores the context of a single dialog turn"""
    user_message: str
    action_plan: list[Action]
    function_calls: List[FunctionCall]

# Debugging
class DebugModel:
    def __init__(self, model_name, model_type):
        self.model_name = model_name
        self.model_type = model_type

    def generate_content(self, prompt, tools=None, safety_settings=None, generation_config=None):
        logging.debug(f"{self.model_name} ({self.model_type}) generating content for prompt: {prompt}")
        time.sleep(1)
        if self.model_type == 'planning':
            # Simulate a more elaborate action plan with some intentional errors
            if "User:" in prompt and "important information" in prompt and "outdated policy" in prompt:
                return DebugResponse(text=json.dumps([
                    {"action_type": "find_text", "action_input_start_variable_name": "", "action_input_end_variable_name": "", "action_text_input": "important information", "find_action_start_variable_name": "info_start", "find_action_end_variable_name": "", "action_explanation": "Find the important information in the document."},
                    {"action_type": "find_text", "action_input_start_variable_name": "", "action_input_end_variable_name": "", "action_text_input": "outdated policy", "find_action_start_variable_name": "outdated_start", "find_action_end_variable_name": "outdated_end", "action_explanation": "Locate the section with outdated policy."},
                    {"action_type": "delete_text", "action_input_start_variable_name": "outdated_start", "action_input_end_variable_name": "outdated_end", "action_text_input": "", "find_action_start_variable_name": "", "find_action_end_variable_name": "", "action_explanation": "Remove the outdated policy section."},
                    {"action_type": "insert_text", "action_input_start_variable_name": "info_end", "action_input_end_variable_name": "", "action_text_input": " New updated information.", "find_action_start_variable_name": "", "find_action_end_variable_name": "", "action_explanation": "Add new information after the important information section."}
                ]))
            else:  
                return DebugResponse(text=json.dumps([
                    {"action_type": "find_text", "action_input_start_variable_name": "", "action_input_end_variable_name": "", "action_text_input": "important data", "find_action_start_variable_name": "data_start", "find_action_end_variable_name": "data_end", "action_explanation": "Find the beginning and end of the section 'important data'"},
                    {"action_type": "replace_text", "action_input_start_variable_name": "data_start", "action_input_end_variable_name": "wrong_end", "action_text_input": "Corrected important data.", "find_action_start_variable_name": "", "find_action_end_variable_name": "", "action_explanation": "Replace the text between 'data_start' and 'wrong_end'"},
                    {"action_type": "insert_text", "action_input_start_variable_name": "data_end", "action_input_end_variable_name": "", "action_text_input": " Additional context.", "find_action_start_variable_name": "", "find_action_end_variable_name": "", "action_explanation": "Add additional context after 'data_end'."}
                ]))
        elif self.model_type == 'fix_planning':
            # Simulate a fixed action plan
            return DebugResponse(text=json.dumps([
                {"action_type": "find_text", "action_input_start_variable_name": "", "action_input_end_variable_name": "", "action_text_input": "important data", "find_action_start_variable_name": "data_start", "find_action_end_variable_name": "data_end", "action_explanation": "Find the beginning and end of the section 'important data'"},
                {"action_type": "replace_text", "action_input_start_variable_name": "data_start", "action_input_end_variable_name": "data_end", "action_text_input": "Corrected important data.", "find_action_start_variable_name": "", "find_action_end_variable_name": "", "action_explanation": "Replace the text between 'data_start' and 'data_end'"},
                {"action_type": "insert_text", "action_input_start_variable_name": "data_end", "action_input_end_variable_name": "", "action_text_input": " Additional context.", "find_action_start_variable_name": "", "find_action_end_variable_name": "", "action_explanation": "Add additional context after 'data_end'."}
            ]))
        elif self.model_type == 'select_find_text_match':
            # Simulate selecting a different match index based on the prompt
            if "multiple matches found" in prompt:
                return DebugResponse(text="1")  # Return index 1
            else:
                return DebugResponse(text="0")  # Return index 0
        elif self.model_type == 'evaluation':
            # Simulate a more nuanced evaluation with specific action suggestions
            if "reject" in prompt.lower():
                return DebugResponse(
                    text=json.dumps({"decision": "reject", "explanation": "The plan includes a deletion of potentially important information without a clear justification. The insertion point for new text is also not well defined."}),
                    function_calls=[
                        {"action_type": "delete_text", "arguments": {"start": 10, "end": 50}, "status": "suggested"},
                        {"action_type": "insert_text", "arguments": {"text": "New updated information.", "position": 50}, "status": "suggested"}
                    ]
                )
            else:
                return DebugResponse(
                    text=json.dumps({"decision": "apply", "explanation": "The plan seems reasonable. The find actions correctly identify the relevant sections, and the replacement and insertion actions are appropriate."}),
                    function_calls=[
                         {"action_type": "find_text", "arguments": {"search_text": "important data"}, "status": "executed"},
                        {"action_type": "replace_text", "arguments": {"start": 10, "end": 40, "new_text": "Corrected important data."}, "status": "suggested"},
                        {"action_type": "insert_text", "arguments": {"text": " Additional context.", "position": 40}, "status": "suggested"}
                    ]
                )
        else:
            return DebugResponse(text="Debug response from unknown model type.")

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
        self.function_call = FunctionCall(**function_call) if function_call else None



class DialogManager:
    _embedding_manager: Optional[EmbeddingManager] = None

    def __init__(self, api_key, debug=False):
        self.debug = debug
        if debug:
            self.planning_model = DebugModel('gemini-1.5-pro-latest', 'planning')
            self.fix_planning_model = DebugModel('gemini-1.5-pro-latest', 'fix_planning')
            self.select_find_text_match_model = DebugModel('gemini-1.5-pro-latest', 'select_find_text_match')
            self.evaluation_model = DebugModel('gemini-1.5-flash-latest', 'evaluation')

            logging.info("DialogManager running in debug mode.")
        else:
            genai.configure(api_key=api_key)
            self.planning_model = genai.GenerativeModel(
                'gemini-1.5-pro-latest',
                safety_settings={
                    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                },
                generation_config={
                    genai.GenerationConfig(
                        response_mime_type="application/json", 
                        response_scheme=list[Action]
                    )
                })
            self.fix_planning_model = genai.GenerativeModel(
                'gemini-1.5-flash-latest',
                safety_settings={
                    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                },
                generation_config={
                    genai.GenerationConfig(
                        response_mime_type="application/json", 
                        response_scheme=list[Action]
                    )
                })
            self.select_find_text_match_model = genai.GenerativeModel(
                'gemini-1.5-flash-latest',
                safety_settings={
                    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                },
                generation_config={
                    genai.GenerationConfig(
                        response_mime_type="application/json", 
                        response_scheme=int
                    )
                })
            self.evaluation_model = genai.GenerativeModel(
                'gemini-1.5-flash-latest',
                safety_settings={
                    "HARM_CATEGORY_HARASSMENT": "BLOCK_NONE",
                    "HARM_CATEGORY_HATE_SPEECH": "BLOCK_NONE",
                    "HARM_CATEGORY_SEXUALLY_EXPLICIT": "BLOCK_NONE",
                    "HARM_CATEGORY_DANGEROUS_CONTENT": "BLOCK_NONE",
                },
                generation_config={
                    genai.GenerationConfig(
                        response_mime_type="application/json", 
                        response_scheme=Evaluation,
                        temperature=0.2,
                    ),
                }
            )
            logging.info("DialogManager initialized with Gemini 1.5 models.")

        self._embedding_manager = EmbeddingManager()
        self.dialog_history: Dict[int, List[DialogTurn]] = {}  # User ID to dialog history


    def start_new_dialog(self, user_id: int):
        """Starts a new dialog for the given user"""
        self.dialog_history[user_id] = []

    def get_response_stream(self, user_id: int, user_message: str, document_id: str, current_content_selection: Optional[List[Dict]] = None):
        """
        Generates a response to the user's message using a two-step prompting strategy.

        Args:
            user_id: The ID of the user.
            user_message: The user's message.
            document_id: The ID of the document being edited.
            current_content_selection: The currently selected content items (optional).

        Returns:
            A dictionary containing the response text and suggested edits.
        """
        logging.info(f"Getting response for user {user_id}, message: {user_message}, document: {document_id}, content selection: {current_content_selection}")

        # Retrieve dialog history
        history = self.dialog_history.get(user_id, [])

        # Prepare relevant content based on selection using EmbeddingManager
        relevant_content_excerpts = []

        # Get the document content
        document_text = str(DocumentManager.get_document_content(document_id, as_string=True))

        if current_content_selection:
            try:
                file_ids = [item['file_id'] for item in current_content_selection if item['content_type'] == 'file_content']
                doc_ids = [item['file_id'] for item in current_content_selection if item['content_type'] == 'document']
                entries = FileContent.query.filter(FileContent.id.in_(file_ids)).all() + Document.query.filter(Document.id.in_(doc_ids)).all()
                file_embeddings_ids = [self._embedding_manager.get_embeddings(entry) for entry in entries] # type: ignore
                
                if file_embeddings_ids:
                    similar_sequences = self._embedding_manager._find_similar_sequences( # type: ignore
                        text=user_message,
                        embedding_ids=file_embeddings_ids,
                        limit=5  # Limit to top 5 relevant sequences
                    )

                    for sequence in similar_sequences:
                        if sequence.file.content_id:
                            relevant_content_excerpts.append((sequence.file.content_id, sequence.sequence_text))
                        elif sequence.file.document_id:
                            relevant_content_excerpts.append((sequence.file.document_id, sequence.sequence_text))

            except Exception as e:
                logging.error(f"Error getting relevant content embeddings: {e}")

        # --- Step 1: Create an Action Plan ---
        action_plan_prompt = self._build_action_plan_prompt(user_message, history, document_text, relevant_content_excerpts)
        
        
        action_plan_response = self.planning_model.generate_content(action_plan_prompt)
        action_plan_str: str = action_plan_response.text # type: ignore
        try:
            # Attempt to parse the action plan as JSON
            action_plan: List[Action] = json.loads(action_plan_str) # type: ignore
        except json.JSONDecodeError:
            logging.error(f"Failed to parse action plan as JSON: {action_plan_response.text}")
            action_plan = []  # or some other default/fallback action plan

        logging.info(f"Generated action plan: {action_plan}")
        yield {"intermediary": {"status" : "generated action plan", "action_plan": action_plan}}

        # --- Step 2: Pre-run the action plan to determine positions and gather necessary data ---
        variable_naming_problems = self._validate_action_plan_variables(action_plan)
        if variable_naming_problems:
            logging.error(f"Failed to generate action plan due to variable naming problems: {variable_naming_problems}")
            yield {"intermediary": {"status" : "fixing action_plan variable naming problems", "action_plan": action_plan, "variable_naming_problems": variable_naming_problems}}

            fix_counter = 0
            while variable_naming_problems and fix_counter < 3:
                # Try to fix the problems by renaming variables
                fix_counter += 1
                logging.info(f"Trying to fix variable naming problems: {variable_naming_problems}")
                action_plan = self._fix_action_plan_variable_naming_with_model(user_message, document_text, action_plan, variable_naming_problems) # type: ignore
                variable_naming_problems = self._validate_action_plan_variables(action_plan)
                if not variable_naming_problems:
                    logging.info(f"Fixed variable naming problems: {variable_naming_problems}")
                    yield {"intermediary": {"status" : "fixed action_plan variable naming problems", "action_plan": action_plan}}
                    break

        variable_positions, variable_position_mistakes, variable_position_problems = self._validate_find_text_actions(document_text, action_plan)
        if variable_position_mistakes:
            logging.info(f"Failed to generate action plan due to find_text action mistakes: {variable_position_mistakes}")
            yield {"intermediary": {"status" : "fixing action_plan variable position mistakes", "action_plan": action_plan, "variable_position_mistakes": variable_position_mistakes, "variable_position_problems": variable_position_problems}}

            fix_counter = 0
            while variable_position_mistakes and fix_counter < 3:
                # Try to fix the problems by renaming variables
                fix_counter += 1
                logging.info(f"Trying to fix find_text action problems: {variable_position_mistakes}")
                action_plan = self._fix_action_plan_find_text_with_model(user_message, document_text, action_plan, variable_position_mistakes) # type: ignore
                variable_positions, variable_position_mistakes, variable_position_problems = self._validate_find_text_actions(document_text, action_plan)
                if not variable_position_mistakes:
                    logging.info(f"Fixed find_text action mistakes: {variable_position_mistakes}")
                    yield {"intermediary": {"status" : "fixed action_plan find_text action problems", "action_plan": action_plan}}
                    
        if variable_position_problems:
            logging.info(f"Failed to generate action plan due to find_text action problems: {variable_position_problems}\n Query the model for resolution.")
            for start_variable, end_variable, problem in variable_position_problems:
                logging.info(f"Problem: {problem}")
                # Build a prompt for the model to fix the action plan
                prompt = "## Action Plan Repair\n\n"
                prompt += f"I have an action plan that has a problem with the find_text action resulting in non-exclusive matches, leading to multiple position being found for the {start_variable} and {end_variable} variable. "
                prompt += "Here is the user message, the document content, the current action plan and the identified problem.\n\n"

                prompt += f"## User Message:\n{user_message}\n\n"

                prompt += f"## Document Context:\n{document_text}\n\n"

                prompt += f"## Current Action Plan:\n{json.dumps(action_plan, indent=2)}\n\n"

                prompt += f"## Problem:\n"
                prompt += f"{problem}\n"

                prompt += "\n## Task:\n"
                prompt += "Select which of the found matches is the correct one and return its index (0-based). If you think that none is correct, return -1. " 

                prompt += "## Selection (int):\n"

                # Query the model
                response = self.fix_planning_model.generate_content(prompt)
                selection_str = response.text
            
                logging.info(f"Model response for fixing non-exlusive matches in action plan: {selection_str}")

                try:
                    selection_index = int(selection_str) # type: ignore
                except ValueError as e:
                    logging.error(f"Failed to parse fix for non-exclusive matches in action plan from model response: {e}")
                    return {"response" : "Failed to generate action plan due to find_text action problems.", "suggested_edits": []}
                if selection_index == -1:
                    logging.info(f"Model response for fixing non-exclusive matches in action plan: No match found.")
                    return {"response" : "Failed to generate action plan due to find_text action problems.", "suggested_edits": []}
                
            # update the fixed variable positions
            variable_positions[start_variable] = variable_positions[start_variable][selection_index] # type: ignore
            variable_positions[end_variable] = variable_positions[end_variable][selection_index] # type: ignore


        yield {"intermediary": {"status": "pre_running"}}

        actions = self._pre_run_actions(variable_positions, action_plan)  # type: ignore
        logging.info(f"Pre-run results: {actions}")

        # --- Step 3: Evaluate the Action Plan ---
        evaluation_prompt = self._build_evaluation_prompt(user_message, history, document_text, actions)
        evaluation_response = self.evaluation_model.generate_content(evaluation_prompt)
        evaluation_text = evaluation_response.text
        logging.info(f"Evaluation response: {evaluation_text}")

        try:
            # Attempt to parse the action plan as JSON
            evaluation = json.loads(evaluation_text) # type: ignore
        except json.JSONDecodeError:
            logging.error(f"Failed to parse evaluation as JSON: {evaluation_text}")
            return {"response" : "Failed to apply the generated actions due to an evaluation error.", "suggested_edits": []}

        if evaluation['decision'] != Decision.APPLY:
            logging.info(f"Evaluation rejected the action plan.")
            return {"response" : f"Failed to apply the generated actions due to the evaluation report: {evaluation['explanation']}.", "suggested_edits": []}
            
        logging.info(f"Generated function calls: {actions}")

        # Update dialog history
        history.append(DialogTurn(
            user_message, 
            action_plan,
            actions,
        ))
        self.dialog_history[user_id] = history

        return {
            "response": evaluation['explanation'],
            "suggested_edits": [fc.to_dict() for fc in actions],
        }

    def _build_action_plan_prompt(self, user_message: str, history: List[DialogTurn], document_text: str, relevant_content: List[Tuple[str, str]]) -> str: 
        """
        Builds the prompt for generating an action plan.
        Now includes relevant file content IDs in the prompt to potentially reference them.
        """
        prompt = "## Dialog History:\n"
        for turn in history:
            prompt += f"User: {turn.user_message}\n"
            past_actions = '\n'.join([str(past_action) for past_action in turn.function_calls]) # type: ignore
            prompt += f"Agent (Actions):\n{past_actions}\n"
            
        # Add relevant content to the prompt
        if relevant_content:
            prompt += f"\n## Relevant Content:\n"
            for content_id, content in relevant_content:
                prompt += f"[{content_id}] {content[:4096]}\n" 
     
        prompt += "\n## Document Context:\n"
        prompt += document_text + "\n" 
        
        
        prompt += "\n## User Message:\n"
        prompt += user_message
        if not user_message.endswith("\n"):
            prompt += "\n"
        prompt += "\n## Task:\nCreate a detailed action plan for responding to the user's request and editing the document. The plan should include specific, actionable steps with exact positions and content for each edit. Consider the dialog history, the current document content, and any relevant content from other documents. Use the provided content ids given by square brackets to refer to files in your plan when you describe the action. Break down the task into the smallest possible steps. Each step must consist of these actions:\n"
        prompt += "- `insert_text(text: str, start: int)`: Insert text at a specific position.\n"
        prompt += "- `delete_text(start: int, end: int)`: Delete text between start and end positions.\n"
        prompt += "- `replace_text(start: int, end: int, new_text: str)`: Replace text between start and end with new text.\n"
        prompt += "- `find_text(search_text: str)`: Find the start and end position of a specific text.\n"
        prompt += "Use `find_text` to determine the positions for the other actions. Do not assume positions without prior confirmation. Always use a find action before delete or replace. When using find, store the resulting indices into well named, unique variables. Use these variables as positional arguments for any subsequent insert, delete or replace.\n"
        prompt += "Output the action plan as a sequence of actions, where each action corresponds to one of the specified functions. Do not perform the actions, only describe them in the plan.\n\n"
        prompt += "## Action Plan:\n"
        return prompt


    def _validate_action_plan_variables(self, action_plan: List[Action]) -> List[str]:
        # 1. Validate variable names and input-output consistency
        problems = []

        output_variables = set()
        input_variables = set()
        for action in action_plan:

            if action['find_action_start_variable_name'] in output_variables:
                problems.append(f"Error: Duplicate start position variable name '{action['find_action_start_variable_name']}' for action {action['action_explanation']} used.")
            output_variables.add(action['find_action_start_variable_name'])

            if action['find_action_end_variable_name'] in output_variables:
                problems.append(f"Error: Duplicate end position variable name '{action['find_action_end_variable_name']}' for action {action['action_explanation']} used.")
            output_variables.add(action['find_action_end_variable_name'])
            
            if action['action_input_start_variable_name'] in input_variables:
                problems.append(f"Error: Duplicate input start position variable name '{action['action_input_start_variable_name']}' for action {action['action_explanation']} used.")
            input_variables.add(action['action_input_start_variable_name'])

            if action['action_input_end_variable_name'] in input_variables:
                problems.append(f"Error: Duplicate input end position variable name '{action['action_input_end_variable_name']}' for action {action['action_explanation']} used.")
            input_variables.add(action['action_input_end_variable_name'])

        missing_inputs = input_variables - output_variables
        unused_outputs = output_variables - input_variables
        
        if missing_inputs:
            problems.append(f"Error: Missing output variables to satisfy inputs: {', '.join(missing_inputs)}")
        if unused_outputs:
            problems.append(f"Warning: Unused output variables: {', '.join(unused_outputs)}")

        return problems
    
    def _fix_action_plan_variable_naming_with_model(self, user_message: str, document_text: str, action_plan: List[Action], problems: List[str]) -> Optional[List[Action]]:
        """
        Attempts to fix variable naming problems in the action plan by querying the model again.

        Args:
            user_message: The original user message.
            history: The dialog history.
            document_text: The document content.
            relevant_content: List of relevant content excerpts.
            action_plan: The action plan with detected problems.
            problems: A list of problems identified by _validate_action_plan_variables.

        Returns:
            A new action plan if the model successfully fixes the problems, otherwise None.
        """
        logging.info("Attempting to fix action plan with model...")

        # Build a prompt for the model to fix the action plan
        prompt = "## Action Plan Repair\n\n"
        prompt += "I have an action plan that has some problems with variable names. "
        prompt += "Here is the user message, the document content, the current action plan and the identified problems.\n\n"

        prompt += f"## User Message:\n{user_message}\n\n"

        prompt += f"## Document Context:\n{document_text}\n\n"

        prompt += f"## Current Action Plan:\n{json.dumps(action_plan, indent=2)}\n\n"

        prompt += f"## Problems:\n"
        for problem in problems:
            prompt += f"- {problem}\n"

        prompt += "\n## Task:\n"
        prompt += "Please generate a new, corrected action plan that addresses the identified variable naming problems and keeps the actions the same. " 
        prompt += "Make sure that:\n"
        prompt += "- All variable names are unique.\n"
        prompt += "- All input variables used in actions have corresponding output variables from previous actions.\n"
        prompt += "- The format of the generated action plan should match the format of the current action plan, it should be a json array of actions\n"
        prompt += "If you cannot fix the problems, return an empty list.\n\n"

        prompt += "## Fixed Action Plan (JSON):\n"

        # Query the model
        response = self.fix_planning_model.generate_content(prompt)
        fixed_action_plan_str = response.text
    
        logging.info(f"Model response for fixing action plan: {fixed_action_plan_str}")

        try:
            fixed_action_plan = json.loads(fixed_action_plan_str) # type: ignore
            if isinstance(fixed_action_plan, list) and all(isinstance(action, dict) for action in fixed_action_plan):
                # Perform basic validation on the structure of each action
                for action in fixed_action_plan:
                    if not all(key in action for key in ['action_type', 'action_input_start_variable_name', 'action_input_end_variable_name', 'action_text_input', 'find_action_start_variable_name', 'find_action_end_variable_name', 'action_explanation']):
                        raise ValueError("Invalid action structure")
            else:
                raise ValueError("Invalid action plan format")
        
        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Failed to parse fixed action plan from model response: {e}")
            return None

        # Validate the fixed action plan
        validation_problems = self._validate_action_plan_variables(fixed_action_plan)
        if validation_problems:
            logging.info(f"Fixed action plan still has problems: {validation_problems}")
           
        return fixed_action_plan
    
    def _fix_action_plan_find_text_with_model(self, user_message: str, document_text: str, action_plan: List[Action], mistakes: List[str]) -> Optional[List[Action]]:
        """
        Attempts to fix find_text action problems in the action plan by querying the model again.

        Args:
            user_message: The original user message.
            document_text: The document content.
            action_plan: The action plan with detected problems in find_text actions.
            problems: A list of problems identified by _validate_find_text_actions, specifically related to find_text.

        Returns:
            A new action plan if the model successfully fixes the problems, otherwise None.
        """
        logging.info("Attempting to fix action plan find_text actions with model...")

        # Build a prompt for the model to fix the action plan
        prompt = "## Action Plan Repair (find_text Actions)\n\n"
        prompt += "I have an action plan that has some problems with `find_text` actions. "
        prompt += "Here is the original user message, the document content, the current action plan, and the identified problems.\n\n"

        prompt += f"## User Message:\n{user_message}\n\n"
        prompt += f"## Document Context:\n{document_text}\n\n"

        prompt += f"## Current Action Plan:\n{json.dumps(action_plan, indent=2)}\n\n"

        prompt += f"## Problems:\n"
        for problem in mistakes:
            prompt += f"- {problem}\n"

        prompt += "\n## Task:\n"
        prompt += "Please generate a new, corrected action plan that addresses the identified problems, specifically in the `find_text` actions. "
        prompt += "Make sure that:\n"
        prompt += "- The `find_text` actions correctly identify the locations of the specified text within the document.\n"
        prompt += "- If the exact text is not found, consider using fuzzy matching to find the closest match, but only if it's a close match with high confidence.\n"
        prompt += "- All variable names are unique and used correctly.\n"
        prompt += "- The format of the generated action plan should match the format of the current action plan, it should be a json array of actions\n"
        prompt += "If you cannot fix the problems, return an empty list.\n\n"

        prompt += "## Fixed Action Plan (JSON):\n"

        # Query the model
      
        response = self.planning_model.generate_content(prompt)
        fixed_action_plan_str = response.text

        logging.debug(f"Model response for fixing action plan: {fixed_action_plan_str}")

        try:
            fixed_action_plan = json.loads(fixed_action_plan_str) # type: ignore
            if isinstance(fixed_action_plan, list) and all(isinstance(action, dict) for action in fixed_action_plan):
                # Perform basic validation on the structure of each action
                for action in fixed_action_plan:
                    if not all(key in action for key in ['action_type', 'action_input_start_variable_name', 'action_input_end_variable_name', 'action_text_input', 'find_action_start_variable_name', 'find_action_end_variable_name', 'action_explanation']):
                        raise ValueError("Invalid action structure")
            else:
                raise ValueError("Invalid action plan format")

        except (json.JSONDecodeError, ValueError) as e:
            logging.error(f"Failed to parse fixed action plan from model response: {e}")
            return None

        # Validate the fixed action plan
        validation_problems = self._validate_action_plan_variables(fixed_action_plan)
        if validation_problems:
            logging.error(f"Fixed action plan still has variable naming problems: {validation_problems}")
            

        # Further validate specifically for find_text issues
        _,find_text_mistakes, _ = self._validate_find_text_actions(document_text, fixed_action_plan)
        if find_text_mistakes:
            logging.error(f"Fixed action plan still has find_text problems: {find_text_mistakes}")
           

        return fixed_action_plan
    
    def _validate_find_text_actions(self, document_text: str, action_plan: List[Action]) -> Tuple[Dict[str, Union[int, List[int]]], List[str], List[Tuple[str, str, str]]]:     
        """
        Validates find_text actions, using fuzzy search to find approximate matches if an exact match fails.

        Args:
            document_text: The document text to search in.
            action_plan: The list of actions.

        Returns:
            A tuple containing:
            - positions: A dictionary mapping variable names to positions (start, end).
            - problems: A list of error messages.
        """
        positions = {}
        mistakes = []
        problems = []

        # Find the positions of the text
        for i, action in enumerate(action_plan):
            if action['action_type'] == ActionType.FIND_TEXT:
                search_text = action['action_text_input']

                # Initialize empty lists for start and end positions for this action
                positions[action['find_action_start_variable_name']] = []
                positions[action['find_action_end_variable_name']] = []

                # 1. Exact Search (using regular expressions to find all occurrences):
                exact_matches = list(re.finditer(re.escape(search_text), document_text))

                if not exact_matches:
                    # 2. Fuzzy Search (if exact search fails):
                    logging.info(f"Action {i + 1}: Exact search for '{search_text}' failed. Trying fuzzy search...")

                    # Find all fuzzy matches above the threshold
                    fuzzy_matches = process.extract(search_text, [document_text], scorer=fuzz.partial_ratio, limit=None)

                    for best_match, score in fuzzy_matches:
                        if score >= 90:  # Use a threshold for fuzzy match acceptance
                            for match in re.finditer(re.escape(best_match), document_text):
                                start_pos = match.start()
                                end_pos = match.end()

                                positions[action['find_action_start_variable_name']].append(start_pos)
                                positions[action['find_action_end_variable_name']].append(end_pos)

                                logging.debug(
                                    f"Action {i + 1}: Used fuzzy match '{best_match}' (score: {score}) for '{search_text}'. "
                                    f"Start: {start_pos}, End: {end_pos}"
                                )
                            # Add a warning message about using fuzzy matches
                            logging.debug(f"Warning: Action {i+1}: Used fuzzy matches for '{search_text}' (best score: {score}).")
                        else:
                            logging.debug(
                                f"Action {i + 1}: Failed to find text '{search_text}' in document "
                                f"(best fuzzy match score below threshold: {score}) for action {action['action_explanation']}"
                            )
                            # Continue to the next action since no good matches were found
                            continue

                else:
                    # Exact matches found
                    for match in exact_matches:
                        start_pos = match.start()
                        end_pos = match.end()
                        positions[action['find_action_start_variable_name']].append(start_pos)
                        positions[action['find_action_end_variable_name']].append(end_pos)

                if not positions[action['find_action_start_variable_name']]:
                    mistakes.append(f"Action {i+1}: Failed to find text '{search_text}' in document for action {action['action_explanation']}")

                if len(positions[action['find_action_start_variable_name']]) != len(positions[action['find_action_end_variable_name']]):
                    raise ValueError(f"Action {i+1}: Mismatch in start and end positions for action {action['action_explanation']}")
                
                if len(positions[action['find_action_start_variable_name']]) > 1:
                    problems.append((action['find_action_start_variable_name'], action['find_action_end_variable_name'], f"Action {i+1}: Multiple matches found for '{search_text}' in document for action {action['action_explanation']}"))
                    continue

                positions[action['find_action_start_variable_name']] = positions[action['find_action_start_variable_name']][0]
                positions[action['find_action_end_variable_name']] = positions[action['find_action_end_variable_name']][0]

        return positions, mistakes, problems
    
    def _pre_run_actions(self, variable_positions: Dict[str, int], action_plan: List[Action]) -> List[FunctionCall]:
        """
        Pre-runs actions to gather necessary data.

        Args:
            variable_positions: The extracted variable positions from the action plan.
            action_plan: The list of actions from the action plan.

        Returns:
            A dictionary containing the results of the pre-run actions.
        """

        logging.debug(f"Pre-running actions {action_plan}")
        

        # 3. Execute other actions based on found positions and inputs
        results : List[FunctionCall] = []
        for i, action in enumerate(action_plan):
            if action['action_type'] != ActionType.FIND_TEXT:
                
                if action['action_type'] == ActionType.INSERT_TEXT:

                    # no position found, skip
                    if not action['action_input_start_variable_name'] in variable_positions:
                        logger.error(f"Action {i+1}: Missing start position variable name for action {action['action_explanation']}")
                        continue
                        
                    # no text specified, skip
                    if not action['action_text_input']:
                        logger.error(f"Action {i+1}: Missing text input for inserting text at {variable_positions[action['action_input_start_variable_name']]} of the action: {action['action_explanation']}")
                        continue

                    results.append(FunctionCall(
                        action_type=ActionType.INSERT_TEXT,
                        arguments={"text": action['action_text_input'], "position": variable_positions[action['action_input_start_variable_name']]},
                        status="suggested"
                    ))
                        
                elif action['action_type'] == ActionType.DELETE_TEXT:
                    # no start position found, skip
                    if not action['action_input_start_variable_name'] in variable_positions:
                        logger.error(f"Action {i+1}: Missing start position variable name for action {action['action_explanation']}")
                        continue

                    # no end position found, skip
                    if not action['action_input_end_variable_name'] in variable_positions:
                        logger.error(f"Action {i+1}: Missing end position variable name for action {action['action_explanation']}")
                        continue

                    results.append(FunctionCall(
                        action_type=ActionType.DELETE_TEXT,
                        arguments={"start": variable_positions[action['action_input_start_variable_name']], "end": variable_positions[action['action_input_end_variable_name']]},
                        status="suggested"
                    ))

                elif action['action_type'] == ActionType.REPLACE_TEXT:
                    # no start position found, skip
                    if not action['action_input_start_variable_name'] in variable_positions:
                        logger.error(f"Action {i+1}: Missing start position variable name for action {action['action_explanation']}")
                        continue

                    # no end position found, skip
                    if not action['action_input_end_variable_name'] in variable_positions:
                        logger.error(f"Action {i+1}: Missing end position variable name for action {action['action_explanation']}")
                        continue

                    # no text specified, skip
                    if not action['action_text_input']:
                        logger.error(f"Action {i+1}: Missing text input for replacing text between {variable_positions[action['action_input_start_variable_name']]} and {variable_positions[action['action_input_end_variable_name']]} of the action: {action['action_explanation']}")
                        continue

                    results.append(FunctionCall(
                        action_type=ActionType.REPLACE_TEXT,
                        arguments={"start": variable_positions[action['action_input_start_variable_name']], "end": variable_positions[action['action_input_end_variable_name']], "new_text": action['action_text_input']},
                        status="suggested"
                    ))
              
        return results
    
    def _build_evaluation_prompt(self, user_message: str, history: List[DialogTurn], document_text: str, actions: List[FunctionCall]) -> str:
        """Builds the prompt for evaluating the action plan."""
        prompt = "## Dialog History:\n"
        for turn in history:
            prompt += f"User: {turn.user_message}\n"
            past_actions = '\n'.join([str(past_action) for past_action in turn.function_calls]) # type: ignore
            prompt += f"Agent (Actions):\n{past_actions}\n"

        prompt += "\n## User Message:\n"
        prompt += user_message
        if not user_message.endswith("\n"):
            prompt += "\n"
        prompt += "\n## Document:\n"
        prompt += document_text + "\n"
        prompt += "\n## Actions:\n"
        prompt += json.dumps(actions)
        prompt += "\n## Task:\nEvaluate the planed actions, do they fullfill the users request? Provide a brief summary of your evaluation and decide whether to proceed with the actions or reject the actions.\n" 
        prompt += "## Summary:\n"
        return prompt


    def apply_edit(self, user_id: int, document_id: int, function_call_id: str, current_start: int, current_end: int, accepted: bool):
        """Applies or rejects a suggested edit."""
        logging.info(f"Applying edit for user {user_id}, document {document_id}, function_call_id {function_call_id}, accepted: {accepted}")
        history: List[DialogTurn] = self.dialog_history.get(user_id, [])
        if not history:
            raise ValueError("No dialog history found for user.")

        logger.debug(f"Current dialog history: {history}")
        # Find the edit in the history (in this case a function call)
        function_call_index = None
        turn_index = None
        for i, turn in enumerate(reversed(history)):
            for j, suggested_function_call in enumerate(turn.function_calls):
                if suggested_function_call.id == function_call_id:
                    function_call_index = j
                    turn_index = len(history) - 1 - i
                    break
            if function_call_index is not None:
                break

        if function_call_index is None:
            raise ValueError("Edit not found.")

        # Access the function call using the found indices
        function_call = history[turn_index].function_calls[function_call_index] # type: ignore
        if function_call.status != "suggested":
            logger.error(f"Function call {function_call.name}[{function_call.id}] is not suggested, but already {function_call.status}")
            raise ValueError(f"Function call {function_call.name}[{function_call.id}] is not suggested, but already {function_call.status}")

        delta = Delta()
        if accepted:
            # Apply the function call
            delta = self._execute_function_calls(current_start, current_end, document_id, function_call)  # type: ignore # Pass a list with a single function call
            function_call.status = "accepted"
            logging.info(f"Function call {function_call.name}[{function_call.id}] executed: {delta}")
        else:
            function_call.status = "rejected"
            logging.info(f"Function call {function_call.name}[{function_call.id}] rejected.")

        logging.debug(f"Updated dialog history: {history}")

        # Update the dialog history
        self.dialog_history[user_id] = history

        return delta
    
    def _execute_function_calls(self, current_start: int, current_end: int, document_id: str, function_call: FunctionCall) -> Delta:
        """Executes a single function call, updates all DialogTurn instances following the current one and returns the resulting delta.

        Args:
            history: The current dialog history.
            document_id: The ID of the document being edited.
            function_call: The FunctionCall to execute.

        Returns:
            A tuple containing the updated history and the Delta object representing the change.
        """
        delta = Delta()
        # document_content = DocumentManager.get_document_content(document_id)
        # original_length = len(document_content)

        if function_call.action_type == ActionType.INSERT_TEXT:
            position = current_start #function_call.arguments['position'] + relative_index_change
            text = function_call.arguments['text']
            delta.retain(position)
            delta.insert(text)
        elif function_call.action_type == ActionType.DELETE_TEXT:
            start = current_start # function_call.arguments['start'] + relative_index_change
            end = current_end # function_call.arguments['end'] + relative_index_change
            delta.retain(start)
            delta.delete(end - start)
        elif function_call.action_type == ActionType.REPLACE_TEXT:
            start = current_start # function_call.arguments['start'] + relative_index_change
            end = current_end #function_call.arguments['end'] + relative_index_change
            new_text = function_call.arguments['new_text']
            delta.retain(start)
            delta.delete(end - start)
            delta.retain(start)
            delta.insert(new_text)
        elif function_call.action_type == ActionType.FIND_TEXT:
            # FIND_TEXT doesn't modify the document, so no delta is generated.
            # It might be used to inform subsequent actions, but is handled in the planning phase.
            pass  # No action needed here for execution
        else:
            logging.warning(f"Unknown action type: {function_call.action_type}")
            return Delta()  # Return empty delta for unknown action

        updated_document = DocumentManager.apply_delta(document_id, delta)
        logger.debug(f"Updated document content: {updated_document}")
        return delta
