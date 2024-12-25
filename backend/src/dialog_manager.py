# backend/src/dialog_manager.py
import logging
from pyexpat import model

from document_manager import DocumentManager
from embedding_manager import EmbeddingManager
from models import FileContent, Document
import time
from typing import List, Dict, Optional, Any, Tuple, Union
from llm_manager import LLMManager
from dialog_types import ActionPlanFormat, ActionType, EditAction, EditActionType, FunctionCall, Decision, Evaluation, DialogTurn, ActionPlan, ListIndex

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
        logging.info(f"Getting response for user {user_id}, message: {user_message}, document: {document_id}, content selection: {current_content_selection}")

        # Retrieve dialog history
        history_start = time.time()
        history = self.dialog_history.get(user_id, [])
        logging.info(f"Retrieved dialog history in {time.time() - history_start:.3f}s")
        history_timing = time.time() - history_start
        # Prepare relevant content based on selection using EmbeddingManager
        relevant_content_excerpts = []

        # Get the document content
        doc_start = time.time()
        document_text = str(DocumentManager.get_document_content(document_id, as_string=True))
        logging.info(f"Retrieved document content in {time.time() - doc_start:.3f}s")
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
        action_plan_prompt = self._build_action_plan_prompt(user_message, history, document_text, relevant_content_excerpts)
        logging.info("Action plan prompt: " + action_plan_prompt)
        
        action_plan: ActionPlan = self.planning_model.generate_content(action_plan_prompt)
        logging.info(f"Generated action plan in {time.time() - plan_start:.3f}s: {str(action_plan)}")
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
                action_plan = self._fix_action_plan_variable_naming_with_model(user_message, document_text, action_plan, variable_naming_problems)
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
                return

        validation_naming_timing = time.time() - validation_start

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
                action_plan = self._fix_action_plan_find_text_with_model(user_message, document_text, action_plan, variable_position_mistakes)
                variable_positions, variable_position_mistakes, variable_position_problems = self._validate_find_text_actions(document_text, action_plan)
                logging.debug(f"Position fix iteration {fix_counter} took {time.time() - iteration_start:.3f}s")
                
                if not variable_position_mistakes:
                    logging.info(f"Fixed find_text action mistakes in {time.time() - mistakes_fix_start:.3f}s")
                    yield {"intermediary": {"status": "fixed action_plan find_text action problems", 
                        "action_plan": str(action_plan)}}
            mistakes_fix_timing = time.time() - mistakes_fix_start
                    
            if variable_position_mistakes:
                logging.info(f"Failed to fix position mistakes after {fix_counter} iterations and {mistakes_fix_timing:.3f}s")
                yield {"response": {"status": "Failed to generate action plan due to find_text action mistakes", 
                    "problems": variable_position_mistakes}}

        if variable_position_problems:
            problems_fix_start = time.time()
            logging.info(f"Failed to generate action plan due to find_text action problems: {variable_position_problems}\n Query the model for resolution.")
            for start_variable, end_variable, problem in variable_position_problems:
                iteration_start = time.time()
                logging.info(f"Problem: {problem}")
                prompt = "## Action Plan Repair\n\n"
                prompt += f"I have an action plan that has a problem with the find_text action resulting in non-exclusive matches, leading to multiple position being found for the {start_variable} and {end_variable} variable. "
                prompt += "Here is the user message, the document content, the current action plan and the identified problem.\n\n"
                prompt += f"## User Message:\n{user_message}\n\n"
                prompt += f"## Document Context:\n{document_text}\n\n"
                prompt += f"## Current Action Plan:\n{str(action_plan)}\n\n"
                prompt += f"## Problem:\n{problem}\n"
                prompt += "\n## Task:\nSelect which of the found matches is the correct one and return its index (0-based). If you think that none is correct, return -1. "
                prompt += "## Selection (int):\n"

                response = self.select_find_text_match_model.generate_content(prompt)
                selection_str = response.text
                logging.info(f"Model response for fixing non-exclusive matches took {time.time() - iteration_start:.3f}s: {selection_str}")

                try:
                    selection_index = int(selection_str)
                except ValueError as e:
                    logging.error(f"Failed to parse fix for non-exclusive matches in action plan from model response: {e}")
                    yield {"response": "Failed to generate action plan due to find_text action problems.", "suggested_edits": []}
                    return

                if selection_index == -1:
                    logging.info(f"Model response for fixing non-exclusive matches in action plan: No match found")
                    yield {"response": "Failed to generate action plan due to find_text action problems.", "suggested_edits": []}
                    return

                yield {"intermediary": {"status": "Fixing match ambiguities", 
                    "problem": problem, 
                    "selection": selection_index}}
                
                variable_positions[start_variable] = variable_positions[start_variable][selection_index]
                variable_positions[end_variable] = variable_positions[end_variable][selection_index]
            
            variable_position_fix_timing = time.time() - problems_fix_start
            logging.info(f"Fixed position problems in {variable_position_fix_timing:.3f}s")

        extracted_variables_positions_timing = time.time() - validation_start
        logging.debug(f"Extracted variables and positions in {extracted_variables_positions_timing:.3f}s: {variable_positions}")
        yield {"intermediary": {"status": "Found text position, pre_running actions", "positions": variable_positions}}

        # Step 3: Pre-run and evaluate actions
        prerun_start = time.time()
        actions = self._pre_run_actions(variable_positions, action_plan)
        prerun_timing = time.time() - prerun_start
        logging.info(f"Pre-run completed in {prerun_timing:.3f}s: {str(actions)}")

        eval_start = time.time()
        evaluation_prompt = self._build_evaluation_prompt(user_message, history, document_text, actions)
        evaluation = self.evaluation_model.generate_content(evaluation_prompt)
        evaluation_timing = time.time() - eval_start
        logging.info(f"Evaluation completed in {evaluation_timing:.3f}s: {evaluation}")

      
        if evaluation.decision != Decision.APPLY:
            logging.info(f"Evaluation rejected the action plan") 
            yield {"response": f"Failed to apply the generated actions due to the evaluation report: {evaluation.explanation}.", 
                    "suggested_edits": []}
            return
                
        logging.info(f"Accepted change, generated function calls")

        # Update dialog history
        history_update_start = time.time()
        history.append(DialogTurn(
            user_message, 
            action_plan,
            actions,
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
            prompt += f"Agent (Actions):\n{past_actions}\n\n"
        
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
- Break down the task into two lists consisting of single actions
- Use provided content ids in [square brackets] when referencing files
- Always use find_text actions to locate positions
- Return an action plan with all required actions, both "find_action" and "edit_action" types
- Return the action plan in the following structured format

## Action Plan Format:
The response should be a JSON object with two main arrays:
1. "find_actions": Array of find operations to locate text positions
2. "edit_actions": Array of edit operations (insert, delete, replace)

### Find Action Structure:
{
    "find_action_start_variable_name": str,  // Variable name to store start position
    "find_action_end_variable_name": str,    // Variable name to store end position
    "find_action_text": str,                 // Text to locate, use only one sentence if "insert_text" will be used with that variable
}

### Edit Action Structure:
{
    "action_type": str,                      // One of: "insert_text", "delete_text", "replace_text"
    "action_input_start_variable_name": str, // Variable name from previous find action (start position)
    "action_input_end_variable_name": str,   // Variable name from previous find action (end position)
    "action_text_input": str,                // Text to insert/replace (null for delete)
    "action_explanation": str                // Brief explanation of the edit operation
}

## Important Rules:
1. Use descriptive but concise variable names for position references
2. Each find action should store positions in uniquely named variables
3. Every edit action must reference position variables from previous find actions
4. Never assume absolute positions without a find action
5. Provide clear, specific explanations for each edit action
6. Consider the full context from dialog history when planning actions
7. Reference relevant content using [content_ids] in explanations

## Action Plan:"""
        
        return prompt


    def _validate_action_plan_variables(self, action_plan: ActionPlan) -> Tuple[List[str], List[str]]:
        # 1. Validate variable names and input-output consistency
        problems = []
        warnings = []
        output_variables = set()
        input_variables = set()
        for action in action_plan.find_actions:

            if len(action.find_action_start_variable_name) > 0:
                if action.find_action_start_variable_name in output_variables:
                    problems.append(f"Error: Duplicate start position variable name '{action.find_action_start_variable_name}'.")
                output_variables.add(action.find_action_start_variable_name)

            if len(action.find_action_end_variable_name) > 0:
                if action.find_action_end_variable_name in output_variables:
                    problems.append(f"Error: Duplicate end position variable name '{action.find_action_end_variable_name}'.")
                output_variables.add(action.find_action_end_variable_name)
            
        for action in action_plan.edit_actions:
            if len(action.action_input_start_variable_name) > 0:
                input_variables.add(action.action_input_start_variable_name)

            if len(action.action_input_end_variable_name) > 0: 
                input_variables.add(action.action_input_end_variable_name)

        missing_inputs = input_variables - output_variables
        unused_outputs = output_variables - input_variables
        
        if missing_inputs:
            problems.append(f"Error: Missing output variables to satisfy inputs: {', '.join(missing_inputs)}")
        if unused_outputs:
            warnings.append(f"Warning: Unused output variables: {', '.join(unused_outputs)}")

        return problems, warnings
    
    def _fix_action_plan_variable_naming_with_model(self, user_message: str, document_text: str, action_plan: ActionPlan, problems: List[str]) -> Optional[ActionPlan]:
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
## Repair Instructions

Create a new action plan that:
1. Fixes all variable naming issues
2. Preserves the exact same editing operations
3. Maintains the original sequence of actions

### Variable Naming Rules:
1. Each variable name must be unique across all actions
2. Variable names should be descriptive and indicate their purpose
3. Format: <purpose>_<location>_<type>
   Examples:
   - header_start_pos
   - list_end_pos
   - paragraph_content_start

### Reference Rules:
1. Edit actions can only reference variables defined by previous find actions
2. Each find action must create two variables: start and end positions
3. Variable pairs should use consistent naming:
   - Bad:  find_start_pos, end_location
   - Good: header_start_pos, header_end_pos

### Output Format:
Return a JSON object with two arrays:
{
    "find_actions": [
        {
            "find_action_start_variable_name": str,
            "find_action_end_variable_name": str,
            "find_action_text": str,
            "action_explanation": str
        }
    ],
    "edit_actions": [
        {
            "action_type": str,
            "action_input_start_variable_name": str,
            "action_input_end_variable_name": str,
            "action_text_input": str,
            "action_explanation": str
        }
    ]
}

Important:
- If you cannot fix all problems, return an empty JSON object: {}
- Do not change the content or order of operations
- Only modify variable names to fix the identified problems
- Keep all other fields (action_type, action_text_input, explanations) exactly the same

## Fixed Action Plan (JSON):"""

        # Query the model
        fixed_action_plan = self.fix_planning_model.generate_content(prompt)
        
    
        logging.info(f"Model response for fixing action plan: {fixed_action_plan}")


        # Validate the fixed action plan
        validation_problems, validation_warnings = self._validate_action_plan_variables(fixed_action_plan)
        if validation_problems:
            logging.info(f"Fixed action plan still has problems: {validation_problems}")

        if validation_warnings:
            logging.info(f"Fixed action plan still has warnings: {validation_warnings}")
           
        return fixed_action_plan
    
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
        prompt += "- If the exact text is not found, consider using fuzzy matching to find the closest match, but only if it's a close match with high confidence.\n"
        prompt += "- All variable names are unique and used correctly.\n"
        prompt += "- The format of the generated action plan should match the format of the current action plan, it should be a json array of actions\n"
        prompt += "If you cannot fix the problems, return an empty list.\n\n"

        prompt += "## Fixed Action Plan (JSON):\n"

        # Query the model
        fixed_action_plan = self.planning_model.generate_content(prompt)
       
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
    
    def _validate_find_text_actions(self, document_text: str, action_plan: ActionPlan) -> Tuple[Dict[str, Union[int, List[int]]], List[str], List[Tuple[str, str, str]]]:     
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
        for i, action in enumerate(action_plan.find_actions):
          
            search_text = action.find_action_text
            logging.info(f"Running search text action for search text: {search_text}")
            # Initialize empty lists for start and end positions for this action
            positions[action.find_action_start_variable_name] = []
            positions[action.find_action_end_variable_name] = []

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

                            positions[action.find_action_start_variable_name].append(start_pos)
                            positions[action.find_action_end_variable_name].append(end_pos)

                            logging.debug(
                                f"Action {i + 1}: Used fuzzy match '{best_match}' (score: {score}) for '{search_text}'. "
                                f"Start: {start_pos}, End: {end_pos}"
                            )
                        # Add a warning message about using fuzzy matches
                        logging.info(f"Warning: Action {i+1}: Used fuzzy matches for '{search_text}' (best score: {score}).")
                    else:
                        logging.info(
                            f"Action {i + 1}: Failed to find text '{search_text}' in document "
                            f"(best fuzzy match score below threshold: {score} for match {best_match})"
                        )
                        # Continue to the next action since no good matches were found
                        continue

            else:
                # Exact matches found
                for match in exact_matches:
                    start_pos = match.start()
                    end_pos = match.end()
                    positions[action.find_action_start_variable_name].append(start_pos)
                    positions[action.find_action_end_variable_name].append(end_pos)

                logging.info(f"Found exact matches: {exact_matches}")

            if not positions[action.find_action_start_variable_name]:
                mistakes.append(f"Action {i+1}: Failed to find text '{search_text}' in document")

            if len(positions[action.find_action_start_variable_name]) != len(positions[action.find_action_end_variable_name]):
                raise ValueError(f"Action {i+1}: Mismatch in start and end positions")
            
            if len(positions[action.find_action_start_variable_name]) > 1:
                problems.append((action.find_action_start_variable_name, action.find_action_end_variable_name, f"Action {i+1}: Multiple matches found for '{search_text}' in document."))
                logging.info("Too many occurences of the text ", search_text, " found")
                continue

            positions[action.find_action_start_variable_name] = positions[action.find_action_start_variable_name][0]
            positions[action.find_action_end_variable_name] = positions[action.find_action_end_variable_name][0]

        return positions, mistakes, problems
    
    def _pre_run_actions(self, variable_positions: Dict[str, int], action_plan: ActionPlan) -> List[FunctionCall]:
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
        for i, action in enumerate(action_plan.edit_actions):
            
                
            if action.action_type == EditActionType.INSERT_TEXT:

                # no position found, skip
                if not action.action_input_start_variable_name in variable_positions:
                    logger.error(f"Action {i+1}: Missing start position variable name for action {action.action_explanation}")
                    continue
                    
                # no text specified, skip
                if not action.action_text_input:
                    logger.error(f"Action {i+1}: Missing text input for inserting text at {variable_positions[action.action_input_start_variable_name]} of the action: {action.action_explanation}")
                    continue

                results.append(FunctionCall(
                    action_type=ActionType.INSERT_TEXT,
                    arguments={"text": action.action_text_input, "position": variable_positions[action.action_input_start_variable_name], "explanation": action.action_explanation},
                    status="suggested"
                ))
                    
            elif action.action_type == EditActionType.DELETE_TEXT:
                # no start position found, skip
                if not action.action_input_start_variable_name in variable_positions:
                    logger.error(f"Action {i+1}: Missing start position variable name for action {action.action_explanation}")
                    continue

                # no end position found, skip
                if not action.action_input_end_variable_name in variable_positions:
                    logger.error(f"Action {i+1}: Missing end position variable name for action {action.action_explanation}")
                    continue

                results.append(FunctionCall(
                    action_type=ActionType.DELETE_TEXT,
                    arguments={"start": variable_positions[action.action_input_start_variable_name], "end": variable_positions[action.action_input_end_variable_name], "explanation": action.action_explanation},
                    status="suggested"
                ))

            elif action.action_type == EditActionType.REPLACE_TEXT:
                # no start position found, skip
                if not action.action_input_start_variable_name in variable_positions:
                    logger.error(f"Action {i+1}: Missing start position variable name for action {action.action_explanation}")
                    continue

                # no end position found, skip
                if not action.action_input_end_variable_name in variable_positions:
                    logger.error(f"Action {i+1}: Missing end position variable name for action {action.action_explanation}")
                    continue

                # no text specified, skip
                if not action.action_text_input:
                    logger.error(f"Action {i+1}: Missing text input for replacing text between {variable_positions[action.action_input_start_variable_name]} and {variable_positions[action.action_input_end_variable_name]} of the action: {action.action_explanation}")
                    continue

                results.append(FunctionCall(
                    action_type=ActionType.REPLACE_TEXT,
                    arguments={"start": variable_positions[action.action_input_start_variable_name], "end": variable_positions[action.action_input_end_variable_name], "new_text": action.action_text_input, "explanation": action.action_explanation},
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
            prompt += "\n"
        
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
