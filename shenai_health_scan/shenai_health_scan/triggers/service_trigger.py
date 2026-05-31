# triggers/service_trigger.py
from __future__ import annotations
from typing import Callable

class ServiceTrigger:
    """ROS 2 service ~/start_scan (std_srvs/Trigger). Always-on baseline trigger."""
    def __init__(self, node, service_name: str = "~/start_scan"):
        self._node = node
        self._name = service_name
        self._srv = None
    def start(self, on_trigger: Callable[[], None]) -> None:
        from std_srvs.srv import Trigger
        def _cb(request, response):
            on_trigger()
            response.success = True
            response.message = "scan requested"
            return response
        self._srv = self._node.create_service(Trigger, self._name, _cb)
        self._node.get_logger().info(f"ServiceTrigger ready on {self._name}")
    def stop(self) -> None:
        if self._srv is not None:
            self._node.destroy_service(self._srv); self._srv = None
