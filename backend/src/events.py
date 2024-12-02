# events.py
from dataclasses import dataclass
from typing import Any, Optional

@dataclass
class WebSocketEvent:
    name: str
    data: Any