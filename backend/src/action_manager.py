from typing import Generator, List
from dialog_types import ActionType, Decision, DialogTurn, FunctionCall, IntermediaryResult, IntermediaryStatus, RefineAction, IntermediaryResult
from llm_manager import LLM

class ActionManager:
    def __init__(self, refining_model: LLM) -> None:
        self.refining_model = refining_model

    def generate_refinement_prompt( self, action: FunctionCall, user_message: str, history: List[DialogTurn], document_text: str, document_html) -> str:
        # Build history section
        prompt = "## Dialog History:\n"
        for turn in history:
            prompt += f"User: {turn.user_message}\n"
            if turn.function_calls:
                prompt += "Agent (Actions):\n"
                for past_action in turn.function_calls:
                    prompt += f"  - {str(past_action)}\n"
            if hasattr(turn, 'decision'):
                prompt += f"Agent (Decision): {turn.decision}\n"
            prompt += "\n"

        # get action context
        if action.action_type == ActionType.INSERT_TEXT:
            action_context = document_text[action.arguments["position"] - 256:action.arguments["position"]]
            action_context += "*START_POSITION*"
            action_context += document_text[action.arguments["position"]:action.arguments["position"] + 256]

            action_formatting_context = document_html[action.arguments["position"] - 256:action.arguments["position"]]
            action_formatting_context += "*START_POSITION*"
            action_formatting_context += document_html[action.arguments["position"]:action.arguments["position"] + 256]
            
        else:
            action_context = document_text[action.arguments["start"] - 256:action.arguments["start"]]
            action_context += "*START_POSITION*"
            action_context += document_text[action.arguments["start"]:action.arguments["end"]]
            action_context += "*END_POSITION*"
            action_context += document_text[action.arguments["end"]:action.arguments["end"] + 256]

            action_formatting_context = document_html[action.arguments["start"] - 256:action.arguments["start"]]
            action_formatting_context += "*START_POSITION*"
            action_formatting_context += document_html[action.arguments["start"]:action.arguments["end"]]
            action_formatting_context += "*END_POSITION*"
            action_formatting_context += document_html[action.arguments["end"]:action.arguments["end"] + 256]

           
        # Add current context
        prompt += f"""## Current User Message:
{user_message}

## Formatted Document Region:
[truncated] {action_formatting_context} [truncated]

## Document Region:
[truncated] {action_context} [truncated]

## Action to Refine:
{str(action)}

## Refinement Task:
You are given the dialog histroy, the current user message, the formatted document region, the document region, and the action to refine.
Prioritize the current user message over the dialog history, but also use the history to guide your refinement.
The formatted document region is the formatted version of the document region, and you should use it to understand the current formatting of the document.
The document region is the selection of the text where the action should be applied. All position changes or selection changes should be based on this text.
Analyze the proposed action and refine its start and end position to perfectly match the user's intentions. 

### Evaluation Criteria:
1. Start Position Accuracy:
- Start position should be exactly where the edit should begin
- No unnecessary leading spaces or characters
- Consider surrounding context for proper positioning

2. End Position Accuracy:
- Must cover the complete region needed for the edit
- Should not include unnecessary surrounding content
- Ignore formatting markers (e.g., list bullets, code block delimiters)

3. User Intent Alignment:
- Action must align with user's explicit or implied intentions
- Reject only if action clearly contradicts user's request
- Consider context from dialog history

"""
        prompt +="""### Response Format:
Return a JSON object matching the RefineAction model:
{
    "decision": "apply" or "reject",
    "explanation": "Brief explanation of your refinement or rejection",
    "start_position_offset": int,  // Adjustment to the start position (positive or negative)
    "end_position_offset": int  // Adjustment to the end position (positive or negative)

### Important Notes:
- Position offset can be positive (move right) or negative (move left)
- Only reject if action fundamentally contradicts user intent
- Partial fulfillment of user request is acceptable
- Consider document structure when refining positions

## Refined Action:"""
        
        return prompt
    
    def _refine_action(self, action: FunctionCall, refinement: RefineAction):
        new_action_arguments = action.arguments.copy()
        if "position" in new_action_arguments:
            new_action_arguments["position"] += refinement.start_position_offset
        if "start" in new_action_arguments:
            new_action_arguments["start"] += refinement.start_position_offset
        if "end" in action.arguments:
            new_action_arguments["end"] += refinement.end_position_offset
        
        new_action = FunctionCall(
            action_type=action.action_type,
            arguments=new_action_arguments,
            status=action.status,
            id=action.id
        )
        return new_action
    
    def refine_actions(self, actions: List[FunctionCall], user_message: str, history: List[DialogTurn], document_text: str, document_html :str) -> Generator[IntermediaryResult, None, None]:
        refined_actions = []
        yield IntermediaryResult(
            type="status", 
            message={
                "status": "refining_actions", 
            }
            )
        for action in actions:
            prompt = self.generate_refinement_prompt(action, user_message, history, document_text, document_html)
            print(f"Refinement prompt: {prompt}")
            try:
                refine_action = self.refining_model.generate_content(prompt)
            except Exception as e:
                yield IntermediaryResult(
                    type="error",
                    message={
                        "status": f"Failed to generate refinement for action",
                        "action": str(action),
                        "prompt": prompt,
                        "error": str(e)
                    }
                )
                continue

            if refine_action.decision == Decision.REJECT:
                yield IntermediaryResult(
                    type="status",
                    message={
                        "status": "Action refinement rejected action",
                        "action": str(action),
                        "prompt": prompt,
                        "decision": refine_action.decision,
                        "explanation": refine_action.explanation
                    }
                )
            
        
            refined_action = self._refine_action(action, refine_action)
            refined_actions.append(refined_action)
            yield IntermediaryResult(
                type="status",
                message={
                    "status": "Action refinement accepted action",
                    "action": str(action),
                    "prompt": prompt,
                    "decision": refine_action.decision,
                    "explanation": refine_action.explanation,
                    "refined_action": str(refined_action)
                }
            )
        yield IntermediaryResult(
            type="response",
            message={
                "status": "finished",
                "actions": actions,
                "prompt": prompt,
                "refined_actions": refined_actions
            }
        )