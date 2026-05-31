# triggers/touch_trigger.py
from __future__ import annotations
from typing import Callable

class TouchTrigger:
    """Starts a scan on a head pat. Subscribes /aima/hal/sensor/touch_head."""
    def __init__(self, node, topic: str = "/aima/hal/sensor/touch_head",
                 event: str = "PAT_TWICE"):
        self._node = node
        self._topic = topic
        self._event_name = event
        self._sub = None
    def start(self, on_trigger: Callable[[], None]) -> None:
        from aimdk_msgs.msg import TouchState
        want = getattr(TouchState, self._event_name)
        def _cb(msg):
            if msg.event_type == want:
                on_trigger()
        self._sub = self._node.create_subscription(TouchState, self._topic, _cb, 10)
        self._node.get_logger().info(
            f"TouchTrigger ready on {self._topic} ({self._event_name})")
    def stop(self) -> None:
        if self._sub is not None:
            self._node.destroy_subscription(self._sub); self._sub = None
