# backend/src/dialog_manager.py
import logging
import time
from typing import Generator, List, Dict, Optional, Union

from bs4 import BeautifulSoup as bs
from delta import Delta

from utils import delta_to_string, delta_to_html
from document_manager import DocumentManager
from embedding_manager import EmbeddingManager
from models import db, FileContent, Document, DialogHistory
from llm_manager import LLMManager
from dialog_types import ActionPlan, ActionType, EditActionType, FormatAction, FormatActionType, ActionPlanFormat, FunctionCall, Decision, Evaluation, DialogTurn, FinalResult, IntermediaryResult, IntermediaryStatus, ListIndex
from action_plan_manager import ActionPlanManager
from dialog_history_manager import DialogHistoryManager
from response_evaluator import ResponseEvaluator

logger = logging.getLogger('eddy_logger')
logger.setLevel(logging.DEBUG)

class DialogManager:
    def __init__(self, llm_manager: LLMManager, debug=False):
        self.llm_manager = llm_manager
        self.debug = debug
        self.planning_model = llm_manager.create_llm(
            "slow", "google", response_format_model=ActionPlan, response_format_json=ActionPlanFormat, model_name="planning"
        )
        self.fix_planning_model = llm_manager.create_llm(
            "slow", "google", response_format_model=ActionPlan, response_format_json=ActionPlanFormat, model_name="fix_planning"
        )
        self.select_find_text_match_model = llm_manager.create_llm(
            "fast", "google", response_format_model=ListIndex, model_name="select_find_text_match"
        )
        self.evaluation_model = llm_manager.create_llm(
            "fast", "google", response_format_model=Evaluation, model_name="evaluation"
        )
        self._embedding_manager = EmbeddingManager()
        self.action_plan_manager = ActionPlanManager(self.planning_model, self.fix_planning_model, self.select_find_text_match_model)
        self.dialog_history_manager = DialogHistoryManager()
        self.response_evaluator = ResponseEvaluator(self.evaluation_model)

    def start_new_dialog(self, user_id: int, document_id: str):
        """Starts a new dialog for the given user"""
        return self.dialog_history_manager.start_new_dialog(user_id, document_id)

    def get_response_stream(self, user_id: int, user_message: str, document_id: str,
                            current_content_selection: Optional[List[Dict]] = None)-> Generator[Union[IntermediaryResult, FinalResult], None, None]:
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
        logging.debug(
            f"Getting response for user {user_id}, message: {user_message}, document: {document_id}, content selection: {current_content_selection}"
        )

        # Retrieve dialog history
        history_start = time.time()
        history_entry = self.dialog_history_manager.get_dialog_history(user_id, document_id)
        if not history_entry:
            history_entry_id = self.start_new_dialog(user_id, document_id)
            history_entry = DialogHistory.query.get(history_entry_id)

        history = history_entry.get_turns()
        logging.info(f"Retrieved dialog history {history}")
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
            relevant_content_timing = self._get_relevant_content_excerpts(current_content_selection, user_message, relevant_content_excerpts)

        # Step 1: Create an Action Plan
        plan_start = time.time()
        action_plan_prompt = self.action_plan_manager._build_action_plan_prompt(user_message, history, document_html,
                                                                           relevant_content_excerpts)
        logging.debug("Action plan prompt: " + action_plan_prompt)
        try:
            action_plan: ActionPlan = self.planning_model.generate_content(action_plan_prompt)
        except Exception as e:
            logging.error(f"Error generating action plan: {e}")
            yield FinalResult(status="error", response="Failed to generate action plan due to an error.", suggested_edits=[])
            self.dialog_history_manager.add_turn(history_entry, user_message,
                                                 ActionPlan(find_actions=[], edit_actions=[], format_actions=[]), [],
                                                 Decision.REJECT)
            return

        logging.debug(f"Generated action plan in {time.time() - plan_start:.3f}s: {str(action_plan)}")
        yield IntermediaryResult(
            type="status", 
            message=IntermediaryStatus(
                status="generated action plan", 
                action_plan=action_plan
                )
            )
       
        plan_timing = time.time() - plan_start

        # Step 2: Validate and fix the action plan
        validation_generator = self.action_plan_manager.validate_and_fix_action_plan(
            user_message, document_html, document_text, action_plan, history_entry
        )

        timings = {}
        positions = {}
        for intermediary_result in validation_generator:
            if intermediary_result.type == "error":
                # Failure or final response from a substep
                yield intermediary_result
                return
            elif intermediary_result.type == "status": 
                # Intermediary step
                yield intermediary_result
            else:
                if isinstance(intermediary_result.message, IntermediaryStatus):
                    # Final result from validate_and_fix_action_plan
                    action_plan = intermediary_result.message.action_plan
                    timings = intermediary_result.message.timings # type: ignore
                    positions = intermediary_result.message.positions
                  

                    logging.debug(
                        f"Extracted variables and positions: {action_plan.find_actions}"
                    )

        yield IntermediaryResult(
            type="status", 
            message=IntermediaryStatus(
                status="Found text position, pre_running actions", 
                action_plan=action_plan,
                positions=positions,
                timings=timings
                )
            )
       
        # Fix invalid formatting actions hidden as edit actions
        action_plan = self.action_plan_manager._fix_action_plan_formatting_actions(action_plan)

        # Step 3: Pre-run and evaluate actions
        prerun_start = time.time()
        actions = self.action_plan_manager._pre_run_actions(action_plan, positions)
        prerun_timing = time.time() - prerun_start
        logging.debug(f"Pre-run completed in {prerun_timing:.3f}s: {str(actions)}")
        yield IntermediaryResult(
            type="status", 
            message=IntermediaryStatus(
                status="pre_run_actions", 
                action_plan=action_plan,
                positions=positions,
                timings=timings
                )
            )
        

        eval_start = time.time()
        evaluation_prompt = self.response_evaluator.build_evaluation_prompt(user_message, history, document_text, actions)
        try:
            evaluation = self.evaluation_model.generate_content(evaluation_prompt)
        except Exception as e:
            logging.error(f"Error generating evaluation: {e}")
            yield FinalResult(status="error", response="Failed to generate action plan due to an error.", suggested_edits=[])
            self.dialog_history_manager.add_turn(history_entry, user_message, action_plan, actions, Decision.REJECT)
            return
        
        evaluation_timing = time.time() - eval_start
        logging.debug(f"Evaluation completed in {evaluation_timing:.3f}s: {evaluation}")

        if evaluation.decision != Decision.APPLY:
            logging.info(f"Evaluation rejected the action plan")
            total_time = time.time() - start_time
            yield FinalResult(
                status="response",
                response=f"Failed to apply the generated actions due to the evaluation report: {evaluation.explanation}.",
                suggested_edits=[],
                timing_info={
                    "total_time": total_time,
                    "history": history_timing,
                    "document_retrieval": doc_timing,
                    "relevant_content": relevant_content_timing,
                    "action_plan_generation": plan_timing,
                    "pre_run": prerun_timing,
                    "evaluation": evaluation_timing
                }
            )
          
            return

        logging.debug(f"Accepted change, generated function calls")

        # Update dialog history
        history_update_start = time.time()
        logging.info("Add new turn to dialog history")
        
        self.dialog_history_manager.add_turn(history_entry, user_message, action_plan, actions, evaluation.decision)
        logging.debug(f"Updated dialog history in {time.time() - history_update_start:.3f}s")

        total_time = time.time() - start_time
        logging.info(f"Total response generation time: {total_time:.3f}s")

        yield FinalResult(
            status="response",
            response=evaluation.explanation,
            suggested_edits=actions,
            timing_info={
                "total_time": total_time,
                "history": history_timing,
                "document_retrieval": doc_timing,
                "relevant_content": relevant_content_timing,
                "action_plan_generation": plan_timing,
                "pre_run": prerun_timing,
                "evaluation": evaluation_timing
            } # evt add timing info from validation generator
        )
        return

    def _get_relevant_content_excerpts(self, current_content_selection, user_message, relevant_content_excerpts):
        embed_start = time.time()
        try:
            file_ids = [item['file_id'] for item in current_content_selection if item['content_type'] == 'file_content']
            doc_ids = [item['file_id'] for item in current_content_selection if item['content_type'] == 'document']
            entries = FileContent.query.filter(FileContent.id.in_(file_ids)).all() + Document.query.filter(
                Document.id.in_(doc_ids)).all()
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

        return time.time() - embed_start

    def apply_edit(self, user_id: int, document_id: str, function_call_id: str, current_start: int, current_end: int,
                   accepted: bool):
        """Applies or rejects a suggested edit."""
        logging.info(
            f"Applying edit for user {user_id}, document {document_id}, function_call_id {function_call_id}, accepted: {accepted}"
        )
        history_entry = self.dialog_history_manager.get_dialog_history(user_id, document_id)
        if not history_entry:
            raise ValueError("No dialog history found for user.")

        history = history_entry.get_turns()

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
        function_call = history[turn_index].function_calls[function_call_index]  # type: ignore
        if function_call.status != "suggested":
            logger.error(f"Function call [{function_call.id}] is not suggested, but already {function_call.status}")
            raise ValueError(
                f"Function call [{function_call.id}] is not suggested, but already {function_call.status}"
            )

        delta = Delta()
        if accepted:
            # Apply the function call
            delta = self._execute_function_calls(current_start, current_end, document_id,
                                                 function_call)  # type: ignore # Pass a list with a single function call
            function_call.status = "accepted"
            logging.info(f"Function call [{function_call.id}] executed: {delta}")
        else:
            function_call.status = "rejected"
            logging.info(f"Function call [{function_call.id}] rejected.")

        logging.debug(f"Updated dialog history: {history}")

        # Update the dialog history
        self.dialog_history_manager.update_dialog_history(history_entry, history)

        return delta

    def _execute_function_calls(self, current_start: int, current_end: int, document_id: str,
                                function_call: FunctionCall) -> Delta:
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
            position = current_start  # function_call.arguments['position'] + relative_index_change
            text = function_call.arguments['text']
            delta.retain(position)
            delta.insert(text)
        elif function_call.action_type == ActionType.DELETE_TEXT:
            start = current_start  # function_call.arguments['start'] + relative_index_change
            end = current_end  # function_call.arguments['end'] + relative_index_change
            delta.retain(start)
            delta.delete(end - start)
        elif function_call.action_type == ActionType.REPLACE_TEXT:
            start = current_start  # function_call.arguments['start'] + relative_index_change
            end = current_end  # function_call.arguments['end'] + relative_index_change
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