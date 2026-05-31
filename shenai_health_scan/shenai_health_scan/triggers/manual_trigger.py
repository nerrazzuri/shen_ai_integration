# triggers/manual_trigger.py
from __future__ import annotations
from typing import Callable, Optional

class ManualTrigger:
    """Programmatic trigger for demo/tests; call fire() to start a scan."""
    def __init__(self):
        self._cb: Optional[Callable[[], None]] = None
    def start(self, on_trigger: Callable[[], None]) -> None:
        self._cb = on_trigger
    def fire(self) -> None:
        if self._cb: self._cb()
    def stop(self) -> None:
        self._cb = None
