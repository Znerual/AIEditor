import enum
from typing import Any, Dict, List, Optional, Union
import typing
import uuid
from dataclasses import dataclass, field
from pydantic import BaseModel

ActionPlanFormat = {
    "type": "object",
    "properties": {
        "find_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "find_action_start_variable_name": {"type": "string"},
                    "find_action_end_variable_name": {"type": "string"},
                    "find_action_text": {"type": "string"},
                },
                "required": ["find_action_start_variable_name", "find_action_end_variable_name", "find_action_text"]
            }
        },
        "edit_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action_type": {"type": "string"},
                    "action_input_start_variable_name": {"type": "string"},
                    "action_input_end_variable_name": {"type": "string"},
                    "action_text_input": {"type": "string"},
                    "action_explanation": {"type": "string"}
                },
                "required": ["action_type", "action_input_start_variable_name", "action_input_end_variable_name", "action_text_input", "action_explanation"]
            }
        }
    },
    "required": ["find_actions", "edit_actions"]
}

class ActionType(enum.Enum):
    INSERT_TEXT = "insert_text"
    DELETE_TEXT = "delete_text"
    REPLACE_TEXT = "replace_text"
    FIND_TEXT = "find_text"

    def __eq__(self, value: object) -> bool:
        if isinstance(value, str):
            return value == self.value
        return super().__eq__(value)
    
    def __str__(self) -> str:
        return self.value

class EditActionType(enum.Enum):
    INSERT_TEXT = "insert_text"
    DELETE_TEXT = "delete_text"
    REPLACE_TEXT = "replace_text"

    def __eq__(self, value: object) -> bool:
        if isinstance(value, str):
            return value == self.value
        return super().__eq__(value)
    
    def __str__(self) -> str:
        return self.value
    
class Decision(enum.Enum):
    APPLY = "apply"
    REJECT = "reject"

    def __str__(self) -> str:
        return self.value
    
    def __eq__(self, value: object) -> bool:
        if isinstance(value, str):
            return value == self.value
        return super().__eq__(value)
    
class ListIndex(BaseModel):
    index: int

class FindAction(BaseModel):
    find_action_start_variable_name: str
    find_action_end_variable_name: str
    find_action_text: str

    def __str__(self) -> str:
        return f"find_text({self.find_action_text}) -> {self.find_action_start_variable_name}, {self.find_action_end_variable_name}"

class EditAction(BaseModel):
    action_type: EditActionType
    action_input_start_variable_name : str
    action_input_end_variable_name : str
    action_text_input: str
    action_explanation: str


    def __str__(self):
        if self.action_type == EditActionType.INSERT_TEXT:
            return f"{str(self.action_type)}(start={self.action_input_start_variable_name}, text={self.action_text_input}) [{self.action_explanation}]"
        
        elif self.action_type == EditActionType.DELETE_TEXT:
            return f"{str(self.action_type)}(start={self.action_input_start_variable_name}, end={self.action_input_end_variable_name}) [{self.action_explanation}]"
        
        elif self.action_type == EditActionType.REPLACE_TEXT:
            return f"{str(self.action_type)}(start={self.action_input_start_variable_name}, end={self.action_input_end_variable_name}, new_text={self.action_text_input}) [{self.action_explanation}]"
        
        else:
            return f"Unknown action type: {self.action_type}"

@dataclass
class FunctionCall:
    """Represents a function call with its arguments and status"""
    action_type: ActionType
    arguments: Dict[str, Any]
    status: Optional[str] = None

    def __post_init__(self):
        self.id = str(uuid.uuid4())

    def to_dict(self):
        """Converts the FunctionCall to a dictionary."""
        return {
            "id": self.id,
            "name": str(self.action_type),
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
        else:
            return f"Unknown action type: {self.action_type}"
        
    def __repr__(self) -> str:
        return self.__str__()        

class Evaluation(BaseModel):
    decision: Decision
    explanation: str

class ActionPlan(BaseModel):
    find_actions: List[FindAction]
    edit_actions: List[EditAction]

    def __str__(self):
        return "\n\t-" + "\n\t-".join([str(action) for action in self.find_actions]) + "\n\t-" + "\n\t-".join([str(action) for action in self.edit_actions])

@dataclass
class DialogTurn:
    """Stores the context of a single dialog turn"""
    user_message: str
    action_plan: ActionPlan
    function_calls: List[FunctionCall]

