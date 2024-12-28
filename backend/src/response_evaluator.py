# backend/src/response_evaluator.py
from typing import List

from dialog_types import DialogTurn, FunctionCall
from llm_manager import LLM, LLMManager

class ResponseEvaluator:
    def __init__(self, evaluation_model: LLM):
        self.evaluation_model = evaluation_model

    def build_evaluation_prompt(self, user_message: str, history: List[DialogTurn], document_text: str,
                                actions: List[FunctionCall]) -> str:
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
        prompt += f"""# Current User Message:
{user_message}
# Current Document:
{document_text}

# Proposed Actions:
{proposed_actions}

# Task:
Evaluate whether the proposed actions should be applied. Consider the following criteria:

- Alignment with User Request:
- Do the actions work towards fulfilling the user's request?
- Partial fulfillment is acceptable if the actions are correct
- Not good formatting actions alone should not be a reason for a rejection
- Actions must not contradict the user's intent
- Safety and Consistency:
- Actions should not result in unintended document changes
- Each edit should have a clear purpose related to the request
- Position variables should be properly referenced

## Acceptance Criteria:
### ACCEPT if actions are:
-     Aligned with user's request (even if partial)
-     Safe and well-defined
-     Properly structured with find operations before edits
### REJECT if actions:
-     Contradict user's intent
-     Could cause unintended changes
-     Are completely unrelated to the request

# Evaluation Response Format:"""
              
        prompt += """
Return a JSON object with:
{
"decision": "apply" or "reject",
"explanation": "Brief explanation of the decision, highlighting key factors"
}"""

        return prompt