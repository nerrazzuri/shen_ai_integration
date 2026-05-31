# triggers/topic_trigger.py
from __future__ import annotations
from typing import Callable

class TopicTrigger:
    """Generic trigger: any message on a std_msgs/Empty topic starts a scan."""
    def __init__(self, node, topic: str = "~/start_scan_topic"):
        self._node = node
        self._topic = topic
        self._sub = None
    def start(self, on_trigger: Callable[[], None]) -> None:
        from std_msgs.msg import Empty
        self._sub = self._node.create_subscription(Empty, self._topic,
                                                   lambda _m: on_trigger(), 10)
        self._node.get_logger().info(f"TopicTrigger ready on {self._topic}")
    def stop(self) -> None:
        if self._sub is not None:
            self._node.destroy_subscription(self._sub); self._sub = None
