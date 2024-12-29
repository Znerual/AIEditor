# backend/src/dialog_history_manager.py
from typing import List

from models import db, DialogHistory
from dialog_types import Decision, DialogTurn, ActionPlan

class DialogHistoryManager:
    def start_new_dialog(self, user_id: int, document_id: str) -> DialogHistory:
        """Starts a new dialog for the given user and document."""
        new_dialog = DialogHistory(user_id=user_id, document_id=document_id, turns=[])
        db.session.add(new_dialog)
        db.session.commit()
        return new_dialog.id

    def get_dialog_history(self, user_id: int, document_id: str) -> DialogHistory:
        """Retrieves the dialog history for the given user and document."""
        history_entry = DialogHistory.query.filter_by(user_id=user_id, document_id=document_id).first()
        return history_entry

    def add_turn(self, history_entry: DialogHistory, user_message: str, action_plan: ActionPlan, function_calls: List, decision: Decision):
        """Adds a new turn to the dialog history."""
        existing_turns = history_entry.turns
        print(f"Existing turns: {existing_turns}")
        new_turn = DialogTurn(user_message, action_plan, function_calls, decision).to_dict()
        print(f"New turn: {new_turn}")
        total_turns = existing_turns + [new_turn]
        history_entry.turns = total_turns
        db.session.commit()
        print(f"Updated turns: {history_entry.turns}")

    def update_dialog_history(self, history_entry: DialogHistory, history: List[DialogTurn]):
        """Updates the dialog history."""
        history_entry.turns = [turn.to_dict() for turn in history]
        db.session.commit()