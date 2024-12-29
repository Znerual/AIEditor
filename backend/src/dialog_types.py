# /backend/src/dialog_types.py
import enum
from typing import Any, Dict, List, Optional, Union, TypedDict
from urllib import response
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
                    "find_action_variable_name": {"type": "string"},
                    "find_action_text": {"type": "string"},
                },
                "required": ["find_action_variable_name", "find_action_text"]
            }
        },
        "edit_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["insert_text", "delete_text", "replace_text"]
                    },
                    "position_variable_name": {"type": "string"},
                    "selection_length": {"type": "integer"},
                    "action_text_input": {"type": "string"},
                    "action_explanation": {"type": "string"}
                },
                "required": ["action_type", "position_variable_name", "selection_length", "action_text_input", "action_explanation"]
            }
        },
        "format_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action_type": {
                        "type": "string",
                        "enum": ["change_heading_level_formatting", "make_list_formatting", "remove_list_formatting", "insert_code_block_formatting", "remove_code_block_formatting", "make_bold_formatting", "remove_bold_formatting", "make_italic_formatting", "remove_italic_formatting", "make_strikethrough_formatting", "remove_strikethrough_formatting", "make_underline_formatting", "remove_underline_formatting"]
                    },
                    "position_variable_name": {"type": "string"},
                    "selection_length": {"type": "integer"},
                    "format_parameter": {"type": "string"},
                    "action_explanation": {"type": "string"}
                },
                "required": ["action_type", "position_variable_name", "selection_length", "format_parameter", "action_explanation"]
            }
        }
    },
    "required": ["find_actions", "edit_actions", "format_actions"]
}



class ActionType(str, enum.Enum):
    INSERT_TEXT = "insert_text"
    DELETE_TEXT = "delete_text"
    REPLACE_TEXT = "replace_text"
    FIND_TEXT = "find_text"
    CHANGE_HEADING_LEVEL_FORMATTING = "change_heading_level_formatting"
    MAKE_LIST_FORMATTING = "make_list_formatting"
    REMOVE_LIST_FORMATTING = "remove_list_formatting"
    INSERT_CODE_BLOCK_FORMATTING = "insert_code_block_formatting"
    REMOVE_CODE_BLOCK_FORMATTING = "remove_code_block_formatting"
    MAKE_BOLD_FORMATTING = "make_bold_formatting"
    REMOVE_BOLD_FORMATTING = "remove_bold_formatting"
    MAKE_ITALIC_FORMATTING = "make_italic_formatting"
    REMOVE_ITALIC_FORMATTING = "remove_italic_formatting"
    MAKE_STRIKETHROUGH_FORMATTING = "make_strikethrough_formatting"
    REMOVE_STRIKETHROUGH_FORMATTING = "remove_strikethrough_formatting"
    MAKE_UNDERLINE_FORMATTING = "make_underline_formatting"
    REMOVE_UNDERLINE_FORMATTING = "remove_underline_formatting"

    def __eq__(self, value: object) -> bool:
        if isinstance(value, str):
            return value == self.value
        return super().__eq__(value)
    
    def __str__(self) -> str:
        return self.value

class EditActionType(str, enum.Enum):
    INSERT_TEXT = "insert_text"
    DELETE_TEXT = "delete_text"
    REPLACE_TEXT = "replace_text"

    def __eq__(self, value: object) -> bool:
        if isinstance(value, str):
            return value == self.value
        return super().__eq__(value)
    
    def __str__(self) -> str:
        return self.value

class FormatActionType(str, enum.Enum):
    CHANGE_HEADING_LEVEL_FORMATTING = "change_heading_level_formatting"
    MAKE_LIST_FORMATTING = "make_list_formatting"
    REMOVE_LIST_FORMATTING = "remove_list_formatting"
    INSERT_CODE_BLOCK_FORMATTING = "insert_code_block_formatting"
    REMOVE_CODE_BLOCK_FORMATTING = "remove_code_block_formatting"
    MAKE_BOLD_FORMATTING = "make_bold_formatting"
    REMOVE_BOLD_FORMATTING = "remove_bold_formatting"
    MAKE_ITALIC_FORMATTING = "make_italic_formatting"
    REMOVE_ITALIC_FORMATTING = "remove_italic_formatting"
    MAKE_STRIKETHROUGH_FORMATTING = "make_strikethrough_formatting"
    REMOVE_STRIKETHROUGH_FORMATTING = "remove_strikethrough_formatting"
    MAKE_UNDERLINE_FORMATTING = "make_underline_formatting"
    REMOVE_UNDERLINE_FORMATTING = "remove_underline_formatting"

    def __eq__(self, value: object) -> bool:
        if isinstance(value, str):
            return value == self.value
        return super().__eq__(value)

    def __str__(self) -> str:
        return self.value

class Decision(str, enum.Enum):
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

class RefineAction(BaseModel):
    decision: Decision
    explanation: str
    start_position_offset: int
    end_position_offset: int

class FindAction(BaseModel):
    find_action_variable_name: str
    find_action_text: str

    def __str__(self) -> str:
        return f"find_text({self.find_action_text}) -> {self.find_action_variable_name}"

class EditAction(BaseModel):
    action_type: EditActionType
    position_variable_name : str
    selection_length : int
    action_text_input: str
    action_explanation: str

    def __str__(self):
        if self.action_type == EditActionType.INSERT_TEXT:
            return f"{str(self.action_type)}(start={self.position_variable_name}, text={self.action_text_input}) [{self.action_explanation}]"

        elif self.action_type == EditActionType.DELETE_TEXT:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == EditActionType.REPLACE_TEXT:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}, new_text={self.action_text_input}) [{self.action_explanation}]"

        else:
            return f"Unknown action type: {self.action_type}"

class FormatAction(BaseModel):
    action_type: FormatActionType
    position_variable_name : str
    selection_length : int
    format_parameter: str
    action_explanation: str

    def __str__(self):
        if self.action_type == FormatActionType.CHANGE_HEADING_LEVEL_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}, new_level={self.format_parameter}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.MAKE_LIST_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.REMOVE_LIST_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.INSERT_CODE_BLOCK_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}, language={self.format_parameter}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.REMOVE_CODE_BLOCK_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.MAKE_BOLD_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.REMOVE_BOLD_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.MAKE_ITALIC_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.REMOVE_ITALIC_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.MAKE_STRIKETHROUGH_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.REMOVE_STRIKETHROUGH_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.MAKE_UNDERLINE_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"

        elif self.action_type == FormatActionType.REMOVE_UNDERLINE_FORMATTING:
            return f"{str(self.action_type)}(start={self.position_variable_name}, length={self.selection_length}) [{self.action_explanation}]"
        else:
            return f"Unknown action type: {self.action_type}"

class FunctionCall:
    """Represents a function call with its arguments and status"""
    action_type: ActionType
    arguments: Dict[str, Any]
    status: Optional[str] = None

    def __init__(self, action_type: ActionType, arguments: Dict[str, Any], status: Optional[str] = None, id: Optional[str] = None):
        self.action_type = action_type
        self.arguments = arguments
        self.status = status
        if id:
            self.id = id
        else:
            self.id = str(uuid.uuid4())

    def to_dict(self):
        """Converts the FunctionCall to a dictionary."""
        return {
            "id": self.id,
            "name": str(self.action_type),
            "arguments": self.arguments,
            "status": self.status
        }
    
    @classmethod
    def from_dict(cls, data: Dict):
        """Creates a FunctionCall object from a dictionary."""
        return FunctionCall(action_type=ActionType(data["name"]), arguments=data["arguments"], status=data["status"], id=data["id"])
    
    def _get_param_str(self):
        return ", ".join([f"{key}={value}" for key, value in self.arguments.items()])

    def __str__(self):
        if self.action_type == ActionType.INSERT_TEXT:
            return f"{self.status} insert_text({self._get_param_str()})"
        elif self.action_type == ActionType.DELETE_TEXT:
            return f"{self.status} delete_text({self._get_param_str()})"
        elif self.action_type == ActionType.REPLACE_TEXT:
            return f"{self.status} replace_text({self._get_param_str()})"
        elif self.action_type == ActionType.CHANGE_HEADING_LEVEL_FORMATTING:
            return f"{self.status} change_heading_level_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.MAKE_LIST_FORMATTING:
            return f"{self.status} make_list_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.REMOVE_LIST_FORMATTING:
            return f"{self.status} remove_list_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.INSERT_CODE_BLOCK_FORMATTING:
            return f"{self.status} insert_code_block_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.REMOVE_CODE_BLOCK_FORMATTING:
            return f"{self.status} remove_code_block_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.MAKE_BOLD_FORMATTING:
            return f"{self.status} make_bold_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.REMOVE_BOLD_FORMATTING:
            return f"{self.status} remove_bold_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.MAKE_ITALIC_FORMATTING:
            return f"{self.status} make_italic_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.REMOVE_ITALIC_FORMATTING:
            return f"{self.status} remove_italic_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.MAKE_STRIKETHROUGH_FORMATTING:
            return f"{self.status} make_strikethrough_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.REMOVE_STRIKETHROUGH_FORMATTING:
            return f"{self.status} remove_strikethrough_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.MAKE_UNDERLINE_FORMATTING:
            return f"{self.status} make_underline_formatting({self._get_param_str()})"
        elif self.action_type == ActionType.REMOVE_UNDERLINE_FORMATTING:
            return f"{self.status} remove_underline_formatting({self._get_param_str()})"
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
    format_actions: List[FormatAction]

    def __str__(self):
        find_action_str = "\n\t-" + "\n\t-".join([str(action) for action in self.find_actions])
        edit_action_str = "\n\t-" + "\n\t-".join([str(action) for action in self.edit_actions])
        format_action_str = "\n\t-" + "\n\t-".join([str(action) for action in self.format_actions])
        return find_action_str + edit_action_str + format_action_str

class DialogTurn:
    """Stores the context of a single dialog turn"""
    def __init__(self, user_message: str, action_plan: ActionPlan, function_calls: List[FunctionCall], decision: Decision):
        self.user_message = user_message
        self.action_plan = action_plan
        self.function_calls = function_calls
        self.decision = decision

    def to_dict(self):
        """Converts the DialogTurn object to a dictionary for serialization."""
        return {
            "user_message": self.user_message,
            "action_plan": self.action_plan.model_dump() if self.action_plan else ActionPlan(find_actions=[], edit_actions=[], format_actions=[]).model_dump(),
            "function_calls": [fc.to_dict() for fc in self.function_calls],
            "decision": str(self.decision)
        }

    @staticmethod
    def from_dict(data: Dict):
        """Creates a DialogTurn object from a dictionary."""
        return DialogTurn(
            user_message=data["user_message"],
            action_plan=ActionPlan(**data["action_plan"]) if data["action_plan"] else ActionPlan(find_actions=[], edit_actions=[], format_actions=[]),
            function_calls=[FunctionCall.from_dict(fc) for fc in data["function_calls"]],
            decision=Decision(data["decision"])
        )
    
@dataclass
class DialogMessage:
    sender: str
    text: str

    def to_dict(self):
        return {
            "sender": self.sender,
            "text": self.text
        }
    
@dataclass
class IntermediaryStatus:
    status: str
    action_plan: ActionPlan
    problems: Optional[List[Any]] = None
    mistakes: Optional[List[str]] = None
    timings: Optional[Dict[str, float]] = None
    positions: Optional[Dict[str, int]] = None
    refined_actions: Optional[List[FunctionCall]] = None

@dataclass
class IntermediaryFixing:
    status: str
    problem: str
    selection: int

@dataclass
class IntermediaryResult:
    """
    Represents an intermediary result yielded by a generator function.
    Can either be a status update or a final response.
    """
    type: str  # 'status' | 'response' | 'error
    message: Union[IntermediaryStatus, IntermediaryFixing, ActionPlan, Dict, List]

class FinalResult:
    status: str # 'error' | 'response'
    response: str
    suggested_edits: List[FunctionCall]
    timing_info: Dict[str, float] = {}

    def __init__(self, status: str, response: str, suggested_edits: List[FunctionCall], timing_info: Dict[str, float] = {}):
        self.status = status
        self.response = response
        self.suggested_edits = suggested_edits
        self.timing_info = timing_info