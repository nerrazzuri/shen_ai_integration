# triggers/base.py
from __future__ import annotations
from typing import Protocol, Callable

class ScanTrigger(Protocol):
    def start(self, on_trigger: Callable[[], None]) -> None: ...
    def stop(self) -> None: ...
