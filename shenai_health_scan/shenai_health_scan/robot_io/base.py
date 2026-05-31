from __future__ import annotations
from typing import Protocol, Dict, Any


class RobotIO(Protocol):
    def speak(self, text: str, priority: int = 6) -> None: ...
    def show(self, view: str, data: Dict[str, Any]) -> None: ...
