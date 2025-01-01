# backend/src/action_plan_manager.py
import logging
import time
from turtle import pos
from typing import Generator, List, Dict, Optional, Tuple, Union

from bs4 import BeautifulSoup as bs
from fuzzywuzzy import fuzz, process
import re

from dialog_types import ActionPlan, ActionType, EditActionType, FormatAction, FormatActionType, FunctionCall, Decision, Evaluation, DialogTurn, IntermediaryStatus, IntermediaryFixing, IntermediaryResult
from llm_manager import LLM
from models import db, DialogHistory

logger = logging.getLogger('eddy_logger')

class ActionPlanManager:
    def __init__(self, planning_model: LLM, fix_planning_model: LLM, select_find_text_match_model: LLM):
        self.planning_model = planning_model
        self.fix_planning_model = fix_planning_model
        self.select_find_text_match_model = select_find_text_match_model

    def _build_action_plan_prompt(self, user_message: str, history: List[DialogTurn], document_text: str,
                                  relevant_content: Optional[List[tuple[str, str]]] = None) -> str:
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
    
    def validate_and_fix_action_plan(self, user_message: str, document_html: str, document_text: str, action_plan: ActionPlan, history_entry: DialogHistory) -> Generator[IntermediaryResult, None, None]:
        """
        Validates the generated action plan, fixes any issues, and extracts variable positions.

        Yields:
            IntermediaryResult objects representing status updates or final responses.

        Returns:
            A tuple containing the fixed action plan, timing information, or None if validation fails.
        """

        # Step 1: Validate variable naming
        validation_start = time.time()
        variable_naming_problems, variable_naming_warnings = self._validate_action_plan_variables(action_plan)

        # Step 2: Fix variable naming problems (if any)
        if variable_naming_problems:
            for intermediary_result in self._handle_variable_naming_problems(
                user_message, 
                document_html, 
                action_plan, 
                variable_naming_problems, 
                variable_naming_warnings, 
                history_entry):
                if intermediary_result.type == "error":
                    # Final step failed
                    yield intermediary_result
                    return
                elif intermediary_result.type == "status":
                    # Intermediary step
                    yield intermediary_result
                else:
                    # Intermediary step
                    if intermediary_result.type == "response" and intermediary_result.message.status == "fixed action_plan variable naming problems": # type: ignore
                        action_plan = intermediary_result.message.action_plan # type: ignore
                        # Update the action_plan after fixing variable_naming_problems
                        variable_naming_problems, variable_naming_warnings = self._validate_action_plan_variables(action_plan)
                    
                    yield IntermediaryResult(
                        type="status",
                        message=IntermediaryStatus(
                            status="fixed action_plan variable naming problems",
                            action_plan=action_plan,
                            problems=variable_naming_problems,
                            mistakes=None
                        )
                    )
            if variable_naming_problems:
                yield IntermediaryResult(
                    type="error",
                    message={
                        "status": "Failed to generate action plan due to unsolved variable naming problems.",
                        "problems": variable_naming_problems
                    }
                )
                return  # Stop if problems persist

        validation_naming_timing = time.time() - validation_start

        # Step 3: Clean action plan (remove HTML tags)
        action_plan = self._clean_action_plan(action_plan)

        # Step 4: Validate find_text actions
        position_validation_start = time.time()
        unique_variable_positions, ambiguous_variable_positions,  variable_position_mistakes, variable_position_problems = self._validate_find_text_actions(document_text, action_plan) 

        # Step 5: Fix find_text mistakes (i.e. no text found)
        mistakes_fix_timing = 0
        if variable_position_mistakes:
            for intermediary_result in self._handle_find_text_mistakes(user_message, document_text, action_plan, variable_position_problems, variable_position_mistakes, history_entry):
                if intermediary_result.type == "error":
                    # Final step failed or an error occurred
                    yield intermediary_result
                    return
                elif intermediary_result.type == "status":
                    # Intermediary step
                    yield intermediary_result
                else:
                    # Intermediary step
                    if isinstance(intermediary_result.message, IntermediaryStatus):
                        if intermediary_result.message.status == "fixed action_plan find_text action problems":
                            action_plan = intermediary_result.message.action_plan
                            unique_variable_positions, ambiguous_positions, variable_position_mistakes, variable_position_problems = self._validate_find_text_actions(document_text, action_plan)
                            yield IntermediaryResult(
                                type="status",
                                message=IntermediaryStatus(
                                    status="fixed action_plan find_text action problems",
                                    action_plan=action_plan,
                                    positions=unique_variable_positions,
                                    problems=None,
                                    mistakes=None
                                )
                            )

            if variable_position_mistakes:
                yield IntermediaryResult(
                    type="error",
                    message={
                        "status": "Failed to generate action plan due to find_text action mistakes",
                        "problems": variable_position_mistakes
                    }
                )
                return  # Stop if mistakes persist

            mistakes_fix_timing = time.time() - position_validation_start

        # Step 6: Fix find_text problems (ambiguous matches)
        variable_position_fix_timing = 0
        if variable_position_problems:
            for intermediary_result in self._handle_find_text_problems(user_message, document_text, action_plan, ambiguous_variable_positions, variable_position_problems, history_entry):
                if intermediary_result.type == "error":
                    yield intermediary_result
                    return
                elif intermediary_result.type == "status":
                    yield intermediary_result
                elif intermediary_result.type == "response":
                    if isinstance(intermediary_result.message, IntermediaryStatus):
                        found_positions = intermediary_result.message.positions
                        if not found_positions:
                            found_positions = {}

                        yield IntermediaryResult(
                            type="status",
                            message=IntermediaryStatus(
                                status="fixed action_plan find_text action problems",
                                action_plan=action_plan,
                                problems=None,
                                mistakes=None,
                                positions=found_positions
                            )
                        )
                        unique_variable_positions.update(found_positions)
                      

            if not unique_variable_positions:
                yield IntermediaryResult(
                    type="error",
                    message={
                        "status": "Failed to generate action plan due to find_text action mistakes",
                        "problems": variable_position_mistakes
                    }
                )
                return # Stop if problems persist
            
            variable_position_fix_timing = time.time() - position_validation_start

        # Step 7: Yield the final result
        yield IntermediaryResult(
            type="response",
            message=IntermediaryStatus(
                status="validated_and_fixed_action_plan",
                action_plan=action_plan,
                positions=unique_variable_positions,
                problems=[],
                mistakes=[],
                timings={
                    "validation_naming": validation_naming_timing,
                    "mistakes_fix": mistakes_fix_timing,
                    "variable_position_fix": variable_position_fix_timing
                }
            )
        )

        return

    def _get_latest_action_plan_from_yields(self, intermediary_result: IntermediaryResult) -> Optional[ActionPlan]:
        """
        Extracts the latest ActionPlan from an IntermediaryResult.
        """
        if intermediary_result.type == "status":
            message = intermediary_result.message
            if isinstance(message, IntermediaryStatus):
                return message.action_plan
        return None


    def _handle_variable_naming_problems(self, user_message: str, document_html: str, action_plan: ActionPlan, variable_naming_problems: List[str], variable_naming_warnings: List[str], history_entry: DialogHistory) -> Generator[IntermediaryResult, None, None]:
        """Handles variable naming problems in the action plan."""
        
        fix_start = time.time()
        logging.error(f"Problems found in generated action plan due to variable naming problems: {variable_naming_problems}")
        
        # First yield: Inform about the start of the fixing process
        yield IntermediaryResult(
            type="status",
            message=IntermediaryStatus(
                status="fixing action_plan variable naming problems",
                action_plan=action_plan,
                problems=variable_naming_problems,
            )
        )

        # Try to fix the problems for up to 3 iterations
        fix_counter = 0
        while variable_naming_problems and fix_counter < 3:
            fix_counter += 1

            # Attempt to fix the action plan using the model
            action_plan_suggestion = self._fix_action_plan_variable_naming_with_model(
                user_message, 
                document_html, 
                action_plan,
                variable_naming_problems,
                variable_naming_warnings
            )

            if action_plan_suggestion is None:
                logging.error("Failed to fix variable naming problems")
                yield IntermediaryResult(
                    type="error",
                    message={
                        "status": "Failed to generate action plan due to variable naming problems.",
                        "suggested_edits": []
                    }
                )
                self._reject_action_plan(history_entry, user_message)
                return

            # Re-validate after fixing attempt
            variable_naming_problems, variable_naming_warnings = self._validate_action_plan_variables(action_plan)
            logging.info(f"Variable naming problems after attempt {fix_counter}: {variable_naming_problems}")
            logging.debug(f"Variable naming warnings after attempt {fix_counter}: {variable_naming_warnings}")

            # If no more problems, yield success status and return
            if not variable_naming_problems:
                yield IntermediaryResult(
                    type="response",
                    message=IntermediaryStatus(
                        status="fixed action_plan variable naming problems",
                        action_plan=action_plan,
                        problems=[],
                        mistakes=None
                    )
                )
                return

        # If problems persist after 3 attempts, yield a failure response
        if variable_naming_problems:
            logging.info(f"Could not fix variable naming problems after {fix_counter} iterations (time taken: {time.time() - fix_start:.3f}s)")
            yield IntermediaryResult(
                type="error",
                message={
                    "status": "Fail to generate action_plan because of naming problems",
                    "problems": variable_naming_problems
                }
            )
            self._reject_action_plan(history_entry, user_message)

        return

    def _handle_find_text_mistakes(self, user_message: str, document_text: str, action_plan: ActionPlan, variable_position_problems: List[Tuple[str, int, str]], variable_position_mistakes: List[str], history_entry: DialogHistory) -> Generator[IntermediaryResult, None, None]:
        """Handles find_text action mistakes in the action plan."""
        mistakes_fix_start = time.time()
        logging.info(f"Failed to generate action plan due to find_text action mistakes: {variable_position_mistakes}")

        # First yield: Inform about the start of the fixing process
        yield IntermediaryResult(
            type="status",
            message=IntermediaryStatus(
                status="fixing action_plan variable position mistakes",
                action_plan=action_plan,
                problems=variable_position_problems,
                mistakes=variable_position_mistakes
            )
        )

        # Try to fix the problems for up to 3 iterations
        fix_counter = 0
        while variable_position_mistakes and fix_counter < 3:
            fix_counter += 1

            # Attempt to fix the action plan using the model
            action_plan_suggestion = self._fix_action_plan_find_text_with_model(
                user_message, 
                document_text,
                action_plan,
                variable_position_mistakes
            )

            # If fixing fails, yield a failure response
            if action_plan_suggestion is None:
                logging.error("Failed to fix find_text action problems")
                yield IntermediaryResult(
                    type="error",
                    message={
                        "status": "Failed to generate action plan due to find_text action problems.",
                        "suggested_edits": []
                    }
                )
                self._reject_action_plan(history_entry, user_message)
                return
            
            action_plan = action_plan_suggestion

            # Re-validate after fixing attempt
            unique_variable_positions, ambiguous_positions, variable_position_mistakes, variable_position_problems = self._validate_find_text_actions(document_text, action_plan)
            logging.debug(f"Position fix iteration {fix_counter} took {time.time() - mistakes_fix_start:.3f}s")

            # If no more mistakes, yield success status
            if not variable_position_mistakes:
                logging.info(f"Fixed find_text action mistakes in {time.time() - mistakes_fix_start:.3f}s")
                yield IntermediaryResult(
                    type="response",
                    message=IntermediaryStatus(
                        status="fixed action_plan find_text action problems",
                        action_plan=action_plan,
                        problems=None,
                        mistakes=None
                    )
                )
                break

        # If mistakes persist after 3 attempts, yield a failure response
        if variable_position_mistakes:
            logging.error(f"Failed to fix position mistakes after {fix_counter} iterations (time taken: {time.time() - mistakes_fix_start:.3f}s)")
            yield IntermediaryResult(
                type="error",
                message={
                    "status": "Failed to generate action plan due to find_text action mistakes",
                    "problems": variable_position_mistakes
                }
            )
            self._reject_action_plan(history_entry, user_message)
            return

        return

    def _handle_find_text_problems(self, user_message: str, document_text: str, action_plan: ActionPlan, variable_positions: Dict[str,  List[int]], variable_position_problems: List[Tuple[str, int, str]], history_entry: DialogHistory):
        """Handles find_text action problems (ambiguous matches) in the action plan."""
        problems_fix_start = time.time()
        logging.info(f"Failed to generate action plan due to find_text action problems: {variable_position_problems}\n Query the model for resolution.")

        unique_variable_positions = {}
        for variable, action_index, problem in variable_position_problems:
            logging.info(f"Problem: {problem}")
            prompt = f"""## Action Plan Repair
I have an action plan that has a problem with a find_text action, resulting in multiple matches.
Here is the user message, the document content, the action plan, problematic action and the identified problem.

## User Message:
{user_message}

## Document Context:
{document_text}

## Action Plan:
{str(action_plan)}

## Problem:
{problem}

## Problematic Action:
{action_plan.find_actions[action_index]}

## Task:
Select which of the {len(variable_positions[variable])} found matches is the correct one and return its index (0-based). 
If you think that none is correct, return -1.

## Selection (int):
"""

            try:
                selection = self.select_find_text_match_model.generate_content(prompt)
            except Exception as e:
                logging.error(f"Error generating fix for non-exclusive matches: {e}")
                yield IntermediaryResult(
                    type="error",
                    message={
                        "status": "Failed to generate action plan due to find_text action problems.",
                        "suggested_edits": []
                    }
                )
                self._reject_action_plan(history_entry, user_message)
                return variable_positions

            logging.debug(f"Model response for fixing non-exclusive matches: {selection.index}")

            if selection.index == -1:
                logging.info("Model response for fixing non-exclusive matches in action plan: No match found")
                yield IntermediaryResult(
                    type="error",
                    message={
                        "status": "Failed to generate action plan due to find_text action problems.",
                        "suggested_edits": []
                    }
                )
                self._reject_action_plan(history_entry, user_message)
                return variable_positions

            yield IntermediaryResult(
                type="status",
                message=IntermediaryFixing(
                    status="Fixing match ambiguities",
                    problem=problem,
                    selection=selection.index
                )
            )

            unique_variable_positions[variable] = variable_positions[variable][selection.index]  # type: ignore

        logging.debug(f"Fixed position problems in {time.time() - problems_fix_start:.3f}s")
        yield IntermediaryResult(
            type="response",
            message=IntermediaryStatus(
                status="Fixed find_text action problems",
                action_plan=action_plan,
                positions=unique_variable_positions
            )     
        )
        return

    def _reject_action_plan(self, history_entry: DialogHistory, user_message: str):
        """Rejects the current action plan and adds a rejection turn to the history."""
        history_entry.add_turn(
            DialogTurn(
                user_message,
                ActionPlan(find_actions=[], edit_actions=[], format_actions=[]),
                [],
                Decision.REJECT
            )
        )
        db.session.commit()
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

    def _fix_action_plan_variable_naming_with_model(self, user_message: str, document_text: str,
                                                    action_plan: ActionPlan, problems: List[str],
                                                    warnings: List[str]) -> Optional[ActionPlan]:
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

    def _fix_action_plan_find_text_with_model(self, user_message: str, document_text: str, action_plan: ActionPlan,
                                            mistakes: List[str]) -> Optional[ActionPlan]:
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
        _,_, find_text_mistakes, _ = self._validate_find_text_actions(document_text, fixed_action_plan)
        if find_text_mistakes:
            logging.error(f"Fixed action plan still has find_text problems: {find_text_mistakes}")

        return fixed_action_plan

    def _validate_find_text_actions(self, document_text: str, action_plan: ActionPlan) -> Tuple[
        Dict[str, int], Dict[str, List[int]], List[str], List[Tuple[str, int, str]]]:
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
        unique_positions = {}
        ambiguous_positions = {}
        mistakes = []
        problems = []

        # Iterate through each find_text action
        for i, action in enumerate(action_plan.find_actions):
            search_text = action.find_action_text
            logging.info(f"Running search text action for search text: '{search_text}'")

            if search_text == "":
                mistakes.append(f"Action {i + 1}: Empty search text")
                continue

            # Initialize an empty list for positions for this action
            ambiguous_positions[action.find_action_variable_name] = []

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

                            ambiguous_positions[action.find_action_variable_name].append(start_pos)

                            logging.debug(
                                f"Action {i + 1}: Used fuzzy match '{best_match}' (score: {score}) for '{search_text}'. "
                                f"Start: {start_pos}"
                            )
                        # Add a warning message about using fuzzy matches
                        logging.info(
                            f"Warning: Action {i + 1}: Used fuzzy matches for '{search_text}' (best score: {score}).")
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
                    ambiguous_positions[action.find_action_variable_name].append(start_pos)

                logging.info(f"Found exact matches: {exact_matches}")

            if not ambiguous_positions[action.find_action_variable_name]:
                mistakes.append(f"Action {i + 1}: Failed to find text '{search_text}' in document")
            elif len(ambiguous_positions[action.find_action_variable_name]) > 1:
                problems.append((action.find_action_variable_name, i,
                                f"Action {i + 1}: Multiple matches at positions {','.join(ambiguous_positions[action.find_action_variable_name])} found for '{search_text}' in document."))
                logging.info(f"Too many occurences of the text '{search_text}' found")
            else:
                # Only one position was found, convert list to single int
                unique_positions[action.find_action_variable_name] = ambiguous_positions[action.find_action_variable_name][0]
                del ambiguous_positions[action.find_action_variable_name]

        return unique_positions, ambiguous_positions, mistakes, problems

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

    def _pre_run_actions(self, action_plan: ActionPlan, positions: Dict[str, int]) -> List[FunctionCall]:
        """
        Pre-runs actions to gather necessary data and map variable names to positions.

        Args:
            action_plan: The list of actions from the action plan.

        Returns:
            A list of FunctionCall objects representing the pre-run actions.
        """

        logging.debug(f"Pre-running actions {action_plan}")

        results: List[FunctionCall] = []

        # Process edit actions
        for i, action in enumerate(action_plan.edit_actions):
            if action.action_type == EditActionType.INSERT_TEXT:
                if not action.action_text_input:
                    logger.error(
                        f"Action {i + 1}: Missing text input for inserting text at of the action: {action.action_explanation}"
                    )
                    continue

                results.append(
                    FunctionCall(
                        action_type=ActionType.INSERT_TEXT,
                        arguments={
                            "text": action.action_text_input,
                            "position": positions[action.position_variable_name],
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type in [EditActionType.DELETE_TEXT, EditActionType.REPLACE_TEXT]:
                start_pos = positions[action.position_variable_name]
                end_pos = positions[action.position_variable_name] + action.selection_length

                if action.action_type == EditActionType.DELETE_TEXT:
                    results.append(
                        FunctionCall(
                            action_type=ActionType.DELETE_TEXT,
                            arguments={
                                "start": start_pos,
                                "end": end_pos,
                                "explanation": action.action_explanation
                            },
                            status="suggested"
                        )
                    )
                else:  # EditActionType.REPLACE_TEXT
                    if not action.action_text_input:
                        logger.error(
                            f"Action {i + 1}: Missing text input for replacing text between {start_pos} and {end_pos} of the action: {action.action_explanation}"
                        )
                        continue
                    results.append(
                        FunctionCall(
                            action_type=ActionType.REPLACE_TEXT,
                            arguments={
                                "start": start_pos,
                                "end": end_pos,
                                "new_text": action.action_text_input,
                                "explanation": action.action_explanation
                            },
                            status="suggested"
                        )
                    )

        # Process format actions
        for i, action in enumerate(action_plan.format_actions):
            start_pos = positions[action.position_variable_name]
            end_pos = positions[action.position_variable_name] + action.selection_length

            if action.action_type == FormatActionType.CHANGE_HEADING_LEVEL_FORMATTING:
                if not action.format_parameter:
                    logger.error(f"Action {i + 1}: Missing level parameter for action {action.action_explanation}")
                    continue
                results.append(
                    FunctionCall(
                        action_type=ActionType.CHANGE_HEADING_LEVEL_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "level": action.format_parameter,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.MAKE_LIST_FORMATTING:
                if not action.format_parameter:
                    logger.error(
                        f"Action {i + 1}: Missing list_type parameter for action {action.action_explanation}"
                    )
                    continue

                results.append(
                    FunctionCall(
                        action_type=ActionType.MAKE_LIST_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "list_type": action.format_parameter,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.REMOVE_LIST_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.REMOVE_LIST_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.INSERT_CODE_BLOCK_FORMATTING:
                if not action.format_parameter:
                    logger.error(f"Action {i + 1}: Missing code parameter for action {action.action_explanation}")
                    continue

                results.append(
                    FunctionCall(
                        action_type=ActionType.INSERT_CODE_BLOCK_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "language": action.format_parameter,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.REMOVE_CODE_BLOCK_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.REMOVE_CODE_BLOCK_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.MAKE_BOLD_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.MAKE_BOLD_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.REMOVE_BOLD_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.REMOVE_BOLD_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.MAKE_ITALIC_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.MAKE_ITALIC_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.REMOVE_ITALIC_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.REMOVE_ITALIC_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.MAKE_STRIKETHROUGH_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.MAKE_STRIKETHROUGH_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.REMOVE_STRIKETHROUGH_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.REMOVE_STRIKETHROUGH_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.MAKE_UNDERLINE_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.MAKE_UNDERLINE_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

            elif action.action_type == FormatActionType.REMOVE_UNDERLINE_FORMATTING:
                results.append(
                    FunctionCall(
                        action_type=ActionType.REMOVE_UNDERLINE_FORMATTING,
                        arguments={
                            "start": start_pos,
                            "end": end_pos,
                            "explanation": action.action_explanation
                        },
                        status="suggested"
                    )
                )

        return results