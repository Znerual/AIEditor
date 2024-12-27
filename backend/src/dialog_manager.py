# backend/src/dialog_manager.py
import logging

from utils import delta_to_string, delta_to_html
from document_manager import DocumentManager
from embedding_manager import EmbeddingManager
from models import FileContent, Document
import time
from typing import List, Dict, Optional, Any, Tuple, Union
from llm_manager import LLMManager
from dialog_types import ActionPlanFormat, ActionType, EditActionType, FormatAction, FormatActionType, FunctionCall, Decision, Evaluation, DialogTurn, ActionPlan, ListIndex
from bs4 import BeautifulSoup as bs
from delta import Delta
import json

import typing_extensions as typing
from fuzzywuzzy import fuzz
from fuzzywuzzy import process
import re

logger = logging.getLogger('eddy_logger')
logger.setLevel(logging.DEBUG)  # Set the minimum logging level

class DialogManager:
    _embedding_manager: Optional[EmbeddingManager] = None

    def __init__(self, llm_manager: LLMManager, debug=False):
        self.llm_manager = llm_manager
        
        self.debug = debug
        self.planning_model = llm_manager.create_llm("slow", "google", response_format_model=ActionPlan, response_format_json=ActionPlanFormat, model_name="planning")
        self.fix_planning_model = llm_manager.create_llm("slow", "google", response_format_model=ActionPlan, response_format_json=ActionPlanFormat, model_name="fix_planning")
        self.select_find_text_match_model = llm_manager.create_llm("fast", "google", response_format_model=ListIndex, model_name="select_find_text_match")
        self.evaluation_model = llm_manager.create_llm("fast", "google", response_format_model=Evaluation, model_name="evaluation")
       
        self._embedding_manager = EmbeddingManager()
        self.dialog_history: Dict[int, List[DialogTurn]] = {}  # User ID to dialog history

    def start_new_dialog(self, user_id: int):
        """Starts a new dialog for the given user"""
        self.dialog_history[user_id] = []

    def get_response_stream(self, user_id: int, user_message: str, document_id: str, current_content_selection: Optional[List[Dict]] = None):
        """
        Generates a response to the user's message using a two-step prompting strategy.
        Now includes detailed timing information for debugging.

        Args:
            user_id: The ID of the user.
            user_message: The user's message.
            document_id: The ID of the document being edited.
            current_content_selection: The currently selected content items (optional).

        Returns:
            A dictionary containing the response text and suggested edits.
        """
        start_time = time.time()
        logging.debug(f"Getting response for user {user_id}, message: {user_message}, document: {document_id}, content selection: {current_content_selection}")

        # Retrieve dialog history
        history_start = time.time()
        history = self.dialog_history.get(user_id, [])
        logging.debug(f"Retrieved dialog history in {time.time() - history_start:.3f}s")
        history_timing = time.time() - history_start
        # Prepare relevant content based on selection using EmbeddingManager
        relevant_content_excerpts = []

        # Get the document content
        doc_start = time.time()
        document_delta = DocumentManager.get_document_content(document_id)
        document_html = delta_to_html(document_delta)
        document_text = delta_to_string(document_delta)        


        logging.debug(f"Retrieved document content in {time.time() - doc_start:.3f}s")
        
        doc_timing = time.time() - doc_start
        relevant_content_timing = 0
        if current_content_selection:
            embed_start = time.time()
            try:
                file_ids = [item['file_id'] for item in current_content_selection if item['content_type'] == 'file_content']
                doc_ids = [item['file_id'] for item in current_content_selection if item['content_type'] == 'document']
                entries = FileContent.query.filter(FileContent.id.in_(file_ids)).all() + Document.query.filter(Document.id.in_(doc_ids)).all()
                file_embeddings_ids = [self._embedding_manager.get_embeddings(entry) for entry in entries]
                
                if file_embeddings_ids:
                    similar_sequences = self._embedding_manager._find_similar_sequences(
                        text=user_message,
                        embedding_ids=file_embeddings_ids,
                        limit=5
                    )

                    for sequence in similar_sequences:
                        if sequence.file.content_id:
                            relevant_content_excerpts.append((sequence.file.content_id, sequence.sequence_text))
                        elif sequence.file.document_id:
                            relevant_content_excerpts.append((sequence.file.document_id, sequence.sequence_text))

                logging.debug(f"Processed embeddings and found similar sequences in {time.time() - embed_start:.3f}s")

            except Exception as e:
                logging.error(f"Error getting relevant content embeddings: {e}")

            relevant_content_timing = time.time() - embed_start

        # Step 1: Create an Action Plan
        plan_start = time.time()
        action_plan_prompt = self._build_action_plan_prompt(user_message, history, document_html, relevant_content_excerpts)
        logging.debug("Action plan prompt: " + action_plan_prompt)
        # print("HTML: " + document_html)
        # print("\n\n")
        # print("Text: " + document_text)
        # print("\n\n")
        # print("Prompt: " + action_plan_prompt)
        # yield {"response" : "Debug Stop", "suggested_edits" : []}
        # return

        try:
            action_plan: ActionPlan = self.planning_model.generate_content(action_plan_prompt)
        except Exception as e:
            logging.error(f"Error generating action plan: {e}")
            yield {"response": "Failed to generate action plan due to an error.", "suggested_edits": []}
            history.append(DialogTurn(
            user_message, 
            ActionPlan(find_actions=[], edit_actions=[], format_actions=[]),
            [],
            Decision.REJECT
            ))
            self.dialog_history[user_id] = history
            return
            
        logging.debug(f"Generated action plan in {time.time() - plan_start:.3f}s: {str(action_plan)}")
        yield {"intermediary": {"status": "generated action plan", "action_plan": str(action_plan)}}
        plan_timing = time.time() - plan_start

        # Step 2: Validate and fix the action plan
        validation_start = time.time()
        variable_naming_problems, variable_naming_warnings = self._validate_action_plan_variables(action_plan)
        if variable_naming_problems:
            fix_start = time.time()
            logging.error(f"Problems found in generated action plan due to variable naming problems: {variable_naming_problems}")
            yield {"intermediary": {"status": "fixing action_plan variable naming problems", 
                "action_plan": str(action_plan), 
                "variable_naming_problems": variable_naming_problems}}

            fix_counter = 0
            while variable_naming_problems and fix_counter < 3:
                iteration_start = time.time()
                fix_counter += 1
                logging.info(f"Trying to fix variable naming problems: {variable_naming_problems}")
                action_plan = self._fix_action_plan_variable_naming_with_model(user_message, document_html, action_plan, variable_naming_problems, variable_naming_warnings) # type: ignore
                variable_naming_problems, variable_naming_warnings = self._validate_action_plan_variables(action_plan)
                logging.info(f"Variable naming problems: {variable_naming_problems}")
                logging.debug(f"Variable naming warnings: {variable_naming_warnings}")
                logging.info(f"Fix iteration {fix_counter} took {time.time() - iteration_start:.3f}s")
                
                if not variable_naming_problems:
                    logging.info(f"Fixed variable naming problems in {time.time() - fix_start:.3f}s")
                    yield {"intermediary": {"status": "fixed action_plan variable naming problems", 
                        "action_plan": str(action_plan)}}
                    break
                    
            if variable_naming_problems:
                logging.info(f"Could not fix variable naming problems after {fix_counter} iterations and {time.time() - fix_start:.3f}s")
                yield {"response": {"status": "Fail to generate action_plan because of naming problems", 
                        "problems": variable_naming_problems}}
                history.append(DialogTurn(
                user_message, 
                ActionPlan(find_actions=[], edit_actions=[], format_actions=[]),
                [],
                Decision.REJECT
                ))
                self.dialog_history[user_id] = history
                return
                

        validation_naming_timing = time.time() - validation_start

        # Remove html tags from search text
        logging.info("Action plan before cleaning: " + str(action_plan))
        action_plan = self._clean_action_plan(action_plan)
        logging.info("Action plan after cleaning: " + str(action_plan))

        position_validation_start = time.time()
        
        variable_positions, variable_position_mistakes, variable_position_problems = self._validate_find_text_actions(document_text, action_plan)
        
        logging.debug(f"Validated positions in {time.time() - position_validation_start:.3f}s")
        mistakes_fix_timing = 0
        if variable_position_mistakes:
            mistakes_fix_start = time.time()
            logging.info(f"Failed to generate action plan due to find_text action mistakes: {variable_position_mistakes}")
            yield {"intermediary": {"status": "fixing action_plan variable position mistakes", 
                "action_plan": str(action_plan), 
                "variable_position_mistakes": variable_position_mistakes, 
                "variable_position_problems": variable_position_problems}}

            fix_counter = 0
            while variable_position_mistakes and fix_counter < 3:
                iteration_start = time.time()
                fix_counter += 1
                logging.info(f"Trying to fix find_text action problems: {variable_position_mistakes}")
                action_plan: ActionPlan = self._fix_action_plan_find_text_with_model(user_message, document_text, action_plan, variable_position_mistakes) # type: ignore
                if action_plan is None:
                    logging.error(f"Failed to fix find_text action problems")
                    yield {"response": "Failed to generate action plan due to find_text action problems.", "suggested_edits": []}
                    history.append(DialogTurn(
                        user_message, 
                        ActionPlan(find_actions=[], edit_actions=[], format_actions=[]),
                        [],
                        Decision.REJECT
                    ))
                    self.dialog_history[user_id] = history
                    return
        
                variable_positions, variable_position_mistakes, variable_position_problems = self._validate_find_text_actions(document_text, action_plan)
                logging.debug(f"Position fix iteration {fix_counter} took {time.time() - iteration_start:.3f}s")
                
                if not variable_position_mistakes:
                    logging.info(f"Fixed find_text action mistakes in {time.time() - mistakes_fix_start:.3f}s")
                    yield {"intermediary": {"status": "fixed action_plan find_text action problems", 
                        "action_plan": str(action_plan)}}
            mistakes_fix_timing = time.time() - mistakes_fix_start
                    
            if variable_position_mistakes:
                logging.error(f"Failed to fix position mistakes after {fix_counter} iterations and {mistakes_fix_timing:.3f}s")
                yield {"response": {"status": "Failed to generate action plan due to find_text action mistakes", 
                    "problems": variable_position_mistakes}}
                history.append(DialogTurn(
                    user_message, 
                    action_plan,
                    [],
                    Decision.REJECT
                ))
                self.dialog_history[user_id] = history
                return

        if variable_position_problems:
            problems_fix_start = time.time()
            logging.info(f"Failed to generate action plan due to find_text action problems: {variable_position_problems}\n Query the model for resolution.")
            for variable, problem in variable_position_problems:
                iteration_start = time.time()
                logging.info(f"Problem: {problem}")
                prompt = "## Action Plan Repair\n\n"
                prompt += f"I have an action plan that has a problem with the find_text action resulting in non-exclusive matches, leading to multiple position being found for the {variable} variable. "
                prompt += "Here is the user message, the document content, the current action plan and the identified problem.\n\n"
                prompt += f"## User Message:\n{user_message}\n\n"
                prompt += f"## Document Context:\n{document_text}\n\n"
                prompt += f"## Current Action Plan:\n{str(action_plan)}\n\n"
                prompt += f"## Problem:\n{problem}\n"
                prompt += "\n## Task:\nSelect which of the found matches is the correct one and return its index (0-based). If you think that none is correct, return -1. "
                prompt += "## Selection (int):\n"

                try:
                    selection = self.select_find_text_match_model.generate_content(prompt)
                except Exception as e:
                    logging.error(f"Error generating fix for non-exclusive matches: {e}")
                    yield {"response": "Failed to generate action plan due to find_text action problems.", "suggested_edits": []}
                    history.append(DialogTurn(
                        user_message, 
                        action_plan,
                        [],
                        Decision.REJECT
                    ))
                    self.dialog_history[user_id] = history
                    return
                    

                logging.debug(f"Model response for fixing non-exclusive matches took {time.time() - iteration_start:.3f}s: {selection.index}")

                if selection.index == -1:
                    logging.info(f"Model response for fixing non-exclusive matches in action plan: No match found")
                    yield {"response": "Failed to generate action plan due to find_text action problems.", "suggested_edits": []}
                    history.append(DialogTurn(
                        user_message, 
                        action_plan,
                        [],
                        Decision.REJECT
                    ))
                    self.dialog_history[user_id] = history
                    return

                yield {"intermediary": {"status": "Fixing match ambiguities", 
                    "problem": problem, 
                    "selection": selection.index}}
                
                variable_positions[variable] : Dict[str, int] = variable_positions[variable][selection.index] # type: ignore
               
            
            variable_position_fix_timing = time.time() - problems_fix_start
            logging.debug(f"Fixed position problems in {variable_position_fix_timing:.3f}s")

        extracted_variables_positions_timing = time.time() - validation_start
        logging.debug(f"Extracted variables and positions in {extracted_variables_positions_timing:.3f}s: {variable_positions}")
        yield {"intermediary": {"status": "Found text position, pre_running actions", "positions": variable_positions}}


        # Fix invalid formatting actions hidded as edit actions
        action_plan = self._fix_action_plan_formatting_actions(action_plan)

        # Step 3: Pre-run and evaluate actions
        prerun_start = time.time()
        actions = self._pre_run_actions(variable_positions, action_plan) # type: ignore
        prerun_timing = time.time() - prerun_start
        logging.debug(f"Pre-run completed in {prerun_timing:.3f}s: {str(actions)}")
        yield {"intermediary": {"status": "pre_run_actions", "actions": str(actions)}}
        eval_start = time.time()
        evaluation_prompt = self._build_evaluation_prompt(user_message, history, document_text, actions)
        try:
            evaluation = self.evaluation_model.generate_content(evaluation_prompt)
        except Exception as e:
            logging.error(f"Error generating evaluation: {e}")
            yield {"response": "Failed to generate action plan due to an error.", "suggested_edits": []}
            history.append(DialogTurn(
                user_message, 
                action_plan,
                actions,
                Decision.REJECT
            ))
            self.dialog_history[user_id] = history
            return
        evaluation_timing = time.time() - eval_start
        logging.debug(f"Evaluation completed in {evaluation_timing:.3f}s: {evaluation}")

      
        if evaluation.decision != Decision.APPLY:
            logging.info(f"Evaluation rejected the action plan") 
            yield {"response": f"Failed to apply the generated actions due to the evaluation report: {evaluation.explanation}.", 
                    "suggested_edits": []}
            return
                
        logging.debug(f"Accepted change, generated function calls")

        # Update dialog history
        history_update_start = time.time()
        history.append(DialogTurn(
            user_message, 
            action_plan,
            actions,
            evaluation.decision
        ))
        self.dialog_history[user_id] = history
        logging.debug(f"Updated dialog history in {time.time() - history_update_start:.3f}s")

        total_time = time.time() - start_time
        logging.info(f"Total response generation time: {total_time:.3f}s")
        
        yield {
            "response": evaluation.explanation, 
            "suggested_edits": [action.to_dict() for action in actions],
            "timing_info": {
                "total_time": total_time,
                "history": history_timing,
                "document_retrieval": doc_timing,
                "relevant_content": relevant_content_timing,
                "action_plan_generation": plan_timing,
                "variable_naming_problems": validation_naming_timing,
                "variable_position_problems_fix": mistakes_fix_timing,
                "extracted_variables_total": extracted_variables_positions_timing,
                "pre_run": prerun_timing,
                "evaluation": evaluation_timing
            }
        }
        return
    def _build_action_plan_prompt(self, user_message: str, history: List[DialogTurn], document_text: str, relevant_content: Optional[List[tuple[str, str]]] = None) -> str:
        prompt = "## Dialog History:\n"
        
        # Add conversation history with past actions
        for turn in history:
            prompt += f"User: {turn.user_message}\n"
            past_actions = '\n'.join([str(past_action) for past_action in turn.function_calls])
            prompt += f"\nAgent (Actions):\n{past_actions}\n"
            prompt += f"Agent (Decision):\n{turn.decision}\n\n"
        
        # Add relevant content if provided
        if relevant_content:
            prompt += "## Relevant Content:\n"
            for content_id, content in relevant_content:
                # Truncate content to reasonable length while preserving context
                truncated_content = content[:4096]
                if len(content) > 4096:
                    truncated_content += "... [truncated]"
                prompt += f"[{content_id}] {truncated_content}\n\n"
        
        # Add current document context if provided
        if document_text:
            prompt += "## Document Context:\n"
            prompt += f"{document_text}\n\n"
        
        # Add current user message
        prompt += f"## User Message:\n{user_message}\n\n"
        
        # Add task description and format specifications
        prompt += """## Task:
Create a detailed action plan for responding to the user's request and editing the document. Follow these guidelines:
- Consider the dialog history, current document content, and content from other referenced files
- Break down the task into three lists consisting of single actions
- Use provided content ids in [square brackets] when referencing files
- Always use a find actions to locate a position
- The find action returns the position where the 'find_action_text' STARTS!
- Actions that require a span must specify the length of the span via the 'selection_length' field
- Note that a span always starts from the 'find_action_text' position
- Return an action plan with all required actions, include 'find_action', 'edit_action' and 'format_action' types
- Find actions are all performed first, therfore, the 'find_action_text' has to be the text in the original document
- Only use format actions to format text (italic, bold, ...) 
- Do not output html or markdown
- Ignore the html tags in the 'find_text' actions 
- Return the action plan in the following structured format

## Action Plan Format:
The response should be a JSON object with two main arrays:
1. "find_actions": Array of find operations to locate text positions
2. "edit_actions": Array of edit operations (insert, delete, replace)
3. "format_actions": Array of formatting operations

### Find Action Structure:
{
    "find_action_variable_name": str,        // Variable name to store start position
    "find_action_text": str,                 // Text to locate, use only one sentence if "insert_text" will be used with that variable
}

### Edit Action Structure:
{
    "action_type": str,                      // One of: "insert_text", "delete_text", "replace_text"
    "position_variable_name": str,           // Variable name from previous find action (start position)
    "selection_length": int,                 // Length of the selection for the edit action
    "action_text_input": str,                // Text to insert/replace (null for delete)
    "action_explanation": str                // Brief explanation of the edit operation
}

### Format Action Structure:
{
    "action_type": str,                      // One of: "change_heading_level_formatting", "make_list_formatting", "remove_list_formatting", "insert_code_block_formatting", "remove_code_block_formatting", "make_bold_formatting", "remove_bold_formatting", "make_italic_formatting", "remove_italic_formatting", "make_strikethrough_formatting", "remove_strikethrough_formatting", "make_underline_formatting", "remove_underline_formatting"
    "position_variable_name": str,           // Variable from find action (start position)
    "selection_length": int,                 // Length of the selection for the format action
    "format_parameter": {                    // Format-specific parameters
        // For change_heading_level_formatting:
        "level": int,                        // New heading level (1-6)
        
        // For make_list_formatting:
        "list_type": str,                    // "ordered" or "unordered"
        
        // For insert_code_block_formatting:
        "language": str                      // Programming language (optional)
    },
    "action_explanation": str                // Explanation of the formatting change
}

## Important Rules:
1. Always use a find action before any edit or format operation
2. Don't use less than five words for the 'find_action_text' of the find action
3. Set the 'selection_length' field for edit and format actions that require a span
4. Use descriptive variable names that indicate the purpose of the position
5. Every edit and format action must reference a variable from a find action
6. Variable names must be unique across all find actions
7. Edit and format actions can use the same variables, if they want to use the same position
8. Provide clear, specific explanations for each edit and format action
9. Consider the full context from dialog history
10. Reference content using [content_ids] in explanations

## Variable Naming Conventions:
- Use format: <purpose>_<location>_<type>
  Examples:
  - header_start_pos
  - code_block_end_pos
  - list_item_start_pos

## Action Plan:"""
        
        return prompt

    def _validate_action_plan_variables(self, action_plan: ActionPlan) -> Tuple[List[str], List[str]]:
        # 1. Validate variable names and input-output consistency
        problems = []
        warnings = []
        output_variables = set()
        input_variables = set()
        for action in action_plan.find_actions:
            if action.find_action_variable_name in output_variables:
                problems.append(f"Error: Duplicate find position variable name '{action.find_action_variable_name}'.")
            
            output_variables.add(action.find_action_variable_name)
            
        for action in action_plan.edit_actions:
            if len(action.position_variable_name) > 0:
                input_variables.add(action.position_variable_name)

            if len(action.position_variable_name) > 0: 
                input_variables.add(action.position_variable_name)

        for action in action_plan.format_actions:
            if len(action.position_variable_name) > 0:
                input_variables.add(action.position_variable_name)

            if len(action.position_variable_name) > 0: 
                input_variables.add(action.position_variable_name)

        missing_inputs = input_variables - output_variables
        unused_outputs = output_variables - input_variables
        
        if missing_inputs:
            problems.append(f"Error: Missing output variables to satisfy inputs: {', '.join(missing_inputs)}")
        if unused_outputs:
            warnings.append(f"Warning: Unused output variables: {', '.join(unused_outputs)}")

        return problems, warnings
    
    def _fix_action_plan_variable_naming_with_model(self, user_message: str, document_text: str, action_plan: ActionPlan, problems: List[str], warnings: List[str]) -> Optional[ActionPlan]:
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
        prompt = """## Action Plan Repair Task

The following action plan has variable naming issues that need to be fixed while preserving the original editing intent.

## Original Context
"""
    # Add relevant context
        prompt += f"""### User Message:
{user_message}

### Document Content:
{document_text}

### Current Action Plan:
{str(action_plan)}

### Identified Problems:
"""
        for problem in problems:
            prompt += f"- {problem}\n"

        prompt += """

### Warnings:
"""
        for warning in warnings:
            prompt += f"- {warning}\n"

        prompt += """
## Repair Instructions

Create a new action plan that:
1. Fixes all variable naming issues
2. Preserves the exact same editing and formatting operations
3. Maintains the original sequence of actions

### Variable Naming Rules:
1. Each variable name must be unique across all find actions
2. Variable names should be descriptive and indicate their purpose
3. Format: <purpose>_<location>_<type>
   Examples:
   - header_start_pos
   - list_end_pos
   - paragraph_content_start

### Reference Rules:
1. Edit and format actions can only reference variables defined by previous find actions
2. Each find action creates one variable, indicating the start of the specified sequence

### Output Format:
Return a JSON object with two arrays:
{
    "find_actions": [
        {
            "position_variable_name": str,
            "find_action_text": str,
        }
    ],
    "edit_actions": [
        {
            "action_type": str,
            "position_variable_name": str,
            "selection_length": int,
            "action_text_input": str,
            "action_explanation": str
        }
    ],
    "format_actions": [
        {
            "action_type": str,
            "position_variable_name": str,
            "selection_length": int,
            "format_parameter": str,
            "action_explanation": str
        }
    ],
}

Important:
- If you cannot fix all problems, return an empty JSON object: {}
- Do not change the content or order of operations
- Only modify variable names to fix the identified problems
- Keep all other fields exactly the same

## Fixed Action Plan (JSON):"""

        # Query the model
        try:
            fixed_action_plan = self.fix_planning_model.generate_content(prompt)
        except Exception as e:
            logging.error(f"Error generating fixed action plan: {e}")
            return None
       
    
        logging.info(f"Model response for fixing action plan: {fixed_action_plan}")

        # Validate the fixed action plan
        validation_problems, validation_warnings = self._validate_action_plan_variables(fixed_action_plan)
        if validation_problems:
            logging.info(f"Fixed action plan still has problems: {validation_problems}")

        if validation_warnings:
            logging.info(f"Fixed action plan still has warnings: {validation_warnings}")
           
        return fixed_action_plan
    
    def _clean_action_plan(self, action_plan: ActionPlan) -> ActionPlan:
        # Remove html tags from find_text actions
        for action in action_plan.find_actions:
            soup = bs(action.find_action_text, "html.parser")
            action.find_action_text = soup.get_text()
        return action_plan
    
    def _fix_action_plan_find_text_with_model(self, user_message: str, document_text: str, action_plan: ActionPlan, mistakes: List[str]) -> Optional[ActionPlan]:
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

        prompt += f"## Current Action Plan:\n{str(action_plan)}\n\n"

        prompt += f"## Problems:\n"
        for problem in mistakes:
            prompt += f"- {problem}\n"

        prompt += "\n## Task:\n"
        prompt += "Please generate a new, corrected action plan that addresses the identified problems, specifically in the `find_text` actions. "
        prompt += "Make sure that:\n"
        prompt += "- The `find_text` actions correctly identify the locations of the specified text within the document.\n"
        prompt += "- All variable names are unique and used correctly.\n"
        prompt += "- The format of the generated action plan should match the format of the current action plan, it should be a json array of actions\n"
        prompt += "If you cannot fix the problems, return an empty list.\n\n"

        prompt += "## Fixed Action Plan (JSON):\n"

        # Query the model
        try:
            fixed_action_plan = self.planning_model.generate_content(prompt)
        except Exception as e:
            logging.error(f"Error generating fixed action plan: {e}")
            return None
        # Validate the fixed action plan
        validation_problems, validation_warnings = self._validate_action_plan_variables(fixed_action_plan)
        if validation_problems:
            logging.error(f"Fixed action plan still has variable naming problems: {validation_problems}")
            
        if validation_warnings:
            logging.info(f"Fixed action plan still has variable naming warnings: {validation_warnings}")

        # Further validate specifically for find_text issues
        _,find_text_mistakes, _ = self._validate_find_text_actions(document_text, fixed_action_plan)
        if find_text_mistakes:
            logging.error(f"Fixed action plan still has find_text problems: {find_text_mistakes}")
           

        return fixed_action_plan
    
    def _validate_find_text_actions(self, document_text: str, action_plan: ActionPlan) -> Tuple[Dict[str, Union[int, List[int]]], List[str], List[Tuple[str, str]]]:
        """
        Validates find_text actions by ensuring the text can be found in the document.
        For actions that require a span, it uses two find_text actions to define the start and end.

        Args:
            document_text: The document text to search in.
            action_plan: The action plan containing find_text actions.

        Returns:
            A tuple containing:
            - positions: A dictionary mapping variable names to positions (int
            - mistakes: A list of error messages for actions that could not be validated.
            - problems: A list of tuples indicating ambiguous matches, with variable name and the ambiguous text.
        """
        positions = {}
        mistakes = []
        problems = []

        # Iterate through each find_text action
        for i, action in enumerate(action_plan.find_actions):
            search_text = action.find_action_text
            logging.info(f"Running search text action for search text: '{search_text}'")

            if search_text == "":
                mistakes.append(f"Action {i+1}: Empty search text")
                continue

            # Initialize an empty list for positions for this action
            positions[action.find_action_variable_name] = []

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
                            
                            positions[action.find_action_variable_name].append(start_pos)
                        
                            logging.debug(
                                f"Action {i + 1}: Used fuzzy match '{best_match}' (score: {score}) for '{search_text}'. "
                                f"Start: {start_pos}"
                            )
                        # Add a warning message about using fuzzy matches
                        logging.info(f"Warning: Action {i+1}: Used fuzzy matches for '{search_text}' (best score: {score}).")
                    else:
                        logging.info(
                            f"Action {i + 1}: Failed to find text '{search_text}' in document "
                            f"(best fuzzy match score below threshold: {score} for match '{best_match}')"
                        )
                        # Continue to the next action since no good matches were found
                        continue

            else:
                # Exact matches found
                for match in exact_matches:
                    start_pos = match.start()
                    positions[action.find_action_variable_name].append(start_pos)
                  
                   
                logging.info(f"Found exact matches: {exact_matches}")

            if not positions[action.find_action_variable_name]:
                mistakes.append(f"Action {i+1}: Failed to find text '{search_text}' in document")
            elif len(positions[action.find_action_variable_name]) > 1:
                problems.append((action.find_action_variable_name, f"Action {i+1}: Multiple matches found for '{search_text}' in document."))
                logging.info(f"Too many occurences of the text '{search_text}' found")
            else:
                # Only one position was found, convert list to single int
                positions[action.find_action_variable_name] = positions[action.find_action_variable_name][0]

        return positions, mistakes, problems
    
    def _fix_action_plan_formatting_actions(self, action_plan: ActionPlan) -> ActionPlan:
        """
        Fixes formatting actions that were mistakenly generated as edit actions.
        This function iterates through edit actions and identifies potential formatting
        actions based on specific patterns in the `action_text_input`. It then converts
        these actions to the appropriate format actions and adds them to the
        `format_actions` list while removing them from the `edit_actions` list.
        """

        new_edit_actions = []

        for i, action in enumerate(action_plan.edit_actions):
            if action.action_type == EditActionType.REPLACE_TEXT:
                # Check for bold and italic formatting (triple ***) first
                if action.action_text_input.startswith("***") and action.action_text_input.endswith("***"):
                    new_format_action_italic = FormatAction(
                        action_type=FormatActionType.MAKE_ITALIC_FORMATTING,
                        position_variable_name=action.position_variable_name,
                        selection_length=action.selection_length,
                        format_parameter="",
                        action_explanation=action.action_explanation
                    )
                    action_plan.format_actions.append(new_format_action_italic)

                    new_format_action_bold = FormatAction(
                        action_type=FormatActionType.MAKE_BOLD_FORMATTING,
                        position_variable_name=action.position_variable_name,
                        selection_length=action.selection_length,
                        format_parameter="",
                        action_explanation=action.action_explanation
                    )
                    action_plan.format_actions.append(new_format_action_bold)

                # Check for bold formatting (double ** or __)
                elif (action.action_text_input.startswith("**") and action.action_text_input.endswith("**")) or \
                    (action.action_text_input.startswith("__") and action.action_text_input.endswith("__")):

                    new_format_action = FormatAction(
                        action_type=FormatActionType.MAKE_BOLD_FORMATTING,
                        position_variable_name=action.position_variable_name,
                        selection_length=action.selection_length,
                        format_parameter="",
                        action_explanation=action.action_explanation
                    )
                    action_plan.format_actions.append(new_format_action)

                # Check for italic formatting (single * or _)
                elif (action.action_text_input.startswith("*") and action.action_text_input.endswith("*")) or \
                    (action.action_text_input.startswith("_") and action.action_text_input.endswith("_")):

                    new_format_action = FormatAction(
                        action_type=FormatActionType.MAKE_ITALIC_FORMATTING,
                        position_variable_name=action.position_variable_name,
                        selection_length=action.selection_length,
                        format_parameter="",
                        action_explanation=action.action_explanation
                    )
                    action_plan.format_actions.append(new_format_action)

                # Check for heading formatting (#)
                elif action.action_text_input.startswith("#"):

                    # Count the number of # symbols to determine the heading level
                    level = action.action_text_input.count("#")
                    if level > 6:
                        level = 6

                    new_format_action = FormatAction(
                        action_type=FormatActionType.CHANGE_HEADING_LEVEL_FORMATTING,
                        position_variable_name=action.position_variable_name,
                        selection_length=action.selection_length,
                        format_parameter=str(level),  # level as a string
                        action_explanation=action.action_explanation
                    )
                    action_plan.format_actions.append(new_format_action)
                else:
                    new_edit_actions.append(action)
            else:
                new_edit_actions.append(action)

        action_plan.edit_actions = new_edit_actions

        return action_plan

    def _pre_run_actions(self, variable_positions: Dict[str, int], action_plan: ActionPlan) -> List[FunctionCall]:
        """
        Pre-runs actions to gather necessary data and map variable names to positions.

        Args:
            variable_positions: The extracted variable positions from the action plan.
            action_plan: The list of actions from the action plan.

        Returns:
            A list of FunctionCall objects representing the pre-run actions.
        """

        logging.debug(f"Pre-running actions {action_plan}")

        results: List[FunctionCall] = []

        # Process edit actions
        for i, action in enumerate(action_plan.edit_actions):
            if action.action_type == EditActionType.INSERT_TEXT:
                if action.position_variable_name not in variable_positions:
                    logger.error(f"Action {i+1}: Missing start position variable name for action {action.action_explanation}")
                    continue
                if not action.action_text_input:
                    logger.error(f"Action {i+1}: Missing text input for inserting text at {variable_positions[action.position_variable_name]} of the action: {action.action_explanation}")
                    continue

                results.append(FunctionCall(
                    action_type=ActionType.INSERT_TEXT,
                    arguments={"text": action.action_text_input, "position": variable_positions[action.position_variable_name], "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type in [EditActionType.DELETE_TEXT, EditActionType.REPLACE_TEXT]:
                if action.position_variable_name not in variable_positions:
                    logger.error(f"Action {i+1}: Missing start position variable name for action {action.action_explanation}")
                    continue

                start_pos = variable_positions[action.position_variable_name]
                end_pos = variable_positions[action.position_variable_name] + action.selection_length

                if action.action_type == EditActionType.DELETE_TEXT:
                    results.append(FunctionCall(
                        action_type=ActionType.DELETE_TEXT,
                        arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                        status="suggested"
                    ))
                else:  # EditActionType.REPLACE_TEXT
                    if not action.action_text_input:
                        logger.error(f"Action {i+1}: Missing text input for replacing text between {start_pos} and {end_pos} of the action: {action.action_explanation}")
                        continue
                    results.append(FunctionCall(
                        action_type=ActionType.REPLACE_TEXT,
                        arguments={"start": start_pos, "end": end_pos, "new_text": action.action_text_input, "explanation": action.action_explanation},
                        status="suggested"
                    ))

        # Process format actions
        for i, action in enumerate(action_plan.format_actions):
            if action.position_variable_name not in variable_positions:
                logger.error(f"Action {i+1}: Missing start position variable name for action {action.action_explanation}")
                continue

            start_pos = variable_positions[action.position_variable_name]
            end_pos = variable_positions[action.position_variable_name] + action.selection_length

            if action.action_type == FormatActionType.CHANGE_HEADING_LEVEL_FORMATTING:
                if not action.format_parameter:
                    logger.error(f"Action {i+1}: Missing level parameter for action {action.action_explanation}")
                    continue
                results.append(FunctionCall(
                    action_type=ActionType.CHANGE_HEADING_LEVEL_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "level": action.format_parameter, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.MAKE_LIST_FORMATTING:
                if not action.format_parameter:
                    logger.error(f"Action {i+1}: Missing list_type parameter for action {action.action_explanation}")
                    continue

                results.append(FunctionCall(
                    action_type=ActionType.MAKE_LIST_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "list_type": action.format_parameter, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.REMOVE_LIST_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.REMOVE_LIST_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.INSERT_CODE_BLOCK_FORMATTING:
                if not action.format_parameter:
                    logger.error(f"Action {i+1}: Missing code parameter for action {action.action_explanation}")
                    continue

                results.append(FunctionCall(
                    action_type=ActionType.INSERT_CODE_BLOCK_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "language": action.format_parameter, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.REMOVE_CODE_BLOCK_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.REMOVE_CODE_BLOCK_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.MAKE_BOLD_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.MAKE_BOLD_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.REMOVE_BOLD_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.REMOVE_BOLD_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.MAKE_ITALIC_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.MAKE_ITALIC_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.REMOVE_ITALIC_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.REMOVE_ITALIC_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.MAKE_STRIKETHROUGH_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.MAKE_STRIKETHROUGH_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.REMOVE_STRIKETHROUGH_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.REMOVE_STRIKETHROUGH_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.MAKE_UNDERLINE_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.MAKE_UNDERLINE_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == FormatActionType.REMOVE_UNDERLINE_FORMATTING:
                results.append(FunctionCall(
                    action_type=ActionType.REMOVE_UNDERLINE_FORMATTING,
                    arguments={"start": start_pos, "end": end_pos, "explanation": action.action_explanation},
                    status="suggested"
                ))

        return results
    
    def _build_evaluation_prompt(self, user_message: str, history: List[DialogTurn], document_text: str, actions: List[FunctionCall]) -> str:
        prompt = "## Dialog History:\n"
        # Add conversation history with past actions
        for turn in history:
            prompt += f"User: {turn.user_message}\n"
            past_actions = '\n  - '.join([str(past_action) for past_action in turn.function_calls])
            if past_actions:
                prompt += f"Agent (Actions):\n  - {past_actions}\n"
            prompt += f"Agent (Decision):\n{turn.decision}\n\n"
        
        # Add current context
        proposed_actions = '\n  - '.join([str(action) for action in actions])
        prompt += f"""## Current User Message:
{user_message}

## Current Document:
{document_text}

## Proposed Actions:
- {proposed_actions}

## Task:
Evaluate whether the proposed actions should be applied. Consider the following criteria:

1. Alignment with User Request:
- Do the actions work towards fulfilling the user's request?
- Partial fulfillment is acceptable if the actions are correct
- Not good formatting actions alone should not be a reason for a rejection
- Actions must not contradict the user's intent

2. Safety and Consistency:
- Actions should not result in unintended document changes
- Each edit should have a clear purpose related to the request
- Position variables should be properly referenced

3. Acceptance Criteria:
- ACCEPT if actions are:
    * Aligned with user's request (even if partial)
    * Safe and well-defined
    * Properly structured with find operations before edits

- REJECT if actions:
    * Contradict user's intent
    * Could cause unintended changes
    * Are completely unrelated to the request

## Evaluation Response Format:"""
        prompt += """
Return a JSON object with:
{
    "decision": "apply" or "reject",
    "explanation": "Brief explanation of the decision, highlighting key factors"
}

## Evaluation:"""
        
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
            logger.error(f"Function call [{function_call.id}] is not suggested, but already {function_call.status}")
            raise ValueError(f"Function call [{function_call.id}] is not suggested, but already {function_call.status}")

        delta = Delta()
        if accepted:
            # Apply the function call
            delta = self._execute_function_calls(current_start, current_end, document_id, function_call)  # type: ignore # Pass a list with a single function call
            function_call.status = "accepted"
            logging.info(f"Function call [{function_call.id}] executed: {delta}")
        else:
            function_call.status = "rejected"
            logging.info(f"Function call [{function_call.id}] rejected.")

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
        elif function_call.action_type == ActionType.CHANGE_HEADING_LEVEL_FORMATTING:
            start = current_start
            end = current_end
            level = function_call.arguments['level']
            delta.retain(start)
            delta.retain(end - start, header=level)
        elif function_call.action_type == ActionType.MAKE_LIST_FORMATTING:
            start = current_start
            end = current_end
            list_type = function_call.arguments['list_type']
            delta.retain(start)
            delta.retain(end - start, list=list_type)
        elif function_call.action_type == ActionType.REMOVE_LIST_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, list=None)
        elif function_call.action_type == ActionType.INSERT_CODE_BLOCK_FORMATTING:
            start = current_start
            end = current_end
            language = function_call.arguments['language']
            delta.retain(start)
            delta.retain(end - start, code=language)
        elif function_call.action_type == ActionType.REMOVE_CODE_BLOCK_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, code=None)
        elif function_call.action_type == ActionType.MAKE_BOLD_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, bold=True)
        elif function_call.action_type == ActionType.REMOVE_BOLD_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, bold=None)
        elif function_call.action_type == ActionType.MAKE_ITALIC_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, italic=True)
        elif function_call.action_type == ActionType.REMOVE_ITALIC_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, italic=None)
        elif function_call.action_type == ActionType.MAKE_STRIKETHROUGH_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, strike=True)
        elif function_call.action_type == ActionType.REMOVE_STRIKETHROUGH_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, strike=None)
        elif function_call.action_type == ActionType.MAKE_UNDERLINE_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, underline=True)
        elif function_call.action_type == ActionType.REMOVE_UNDERLINE_FORMATTING:
            start = current_start
            end = current_end
            delta.retain(start)
            delta.retain(end - start, underline=None)
        else:
            logging.warning(f"Unknown action type: {function_call.action_type}")
            return Delta()  # Return empty delta for unknown action

        updated_document = DocumentManager.apply_delta(document_id, delta)
        logger.debug(f"Updated document content: {updated_document}")
        return delta