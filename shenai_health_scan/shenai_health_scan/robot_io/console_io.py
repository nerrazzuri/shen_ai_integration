from __future__ import annotations
from typing import Dict, Any


class ConsoleIO:
    def speak(self, text: str, priority: int = 6) -> None:
        print(f"[TTS] {text}")

    def show(self, view: str, data: Dict[str, Any]) -> None:
        print(f"[SCREEN:{view}] {data}")
