# node.py
from __future__ import annotations
import rclpy
from rclpy.node import Node
from .core.config import ScanConfig
from .runner import ScanApp
from .engine.shenai_engine import ShenAiEngine
from .camera.ros_camera import RosCamera
from .robot_io.ros_io import RosIO
from .triggers.service_trigger import ServiceTrigger
from .triggers.touch_trigger import TouchTrigger
from .triggers.topic_trigger import TopicTrigger

_TRIGGER_FACTORIES = {
    "service": lambda node, cfg: ServiceTrigger(node),
    "touch": lambda node, cfg: TouchTrigger(node),
    "topic": lambda node, cfg: TopicTrigger(node),
}

class ShenAiHealthScanNode(Node):
    def __init__(self):
        super().__init__("shenai_health_scan")
        cfg = self._load_config()
        engine = ShenAiEngine(cfg)
        camera = RosCamera(self, cfg.camera_topic)
        robot_io = RosIO(self)
        triggers = [_TRIGGER_FACTORIES[t](self, cfg)
                    for t in cfg.enabled_triggers if t in _TRIGGER_FACTORIES]
        self.app = ScanApp(cfg, camera=camera, engine=engine, robot_io=robot_io,
                           triggers=triggers, logger=self.get_logger().warn)
        self.app.start()
        self.get_logger().info("Shen.AI health scan node started.")

    def _load_config(self) -> ScanConfig:
        self.declare_parameters("", [
            ("api_key", ""), ("offline", False),
            ("measurement_preset", "ONE_MINUTE_ALL_METRICS"),
            ("precision_mode", "RELAXED"),
            ("camera_topic", "/aima/hal/sensor/rgbd_head_front/rgb_image"),
            ("submit_fps", 30),
            ("enabled_triggers", ["service"]),
            ("acquire_face_timeout", 20.0), ("max_measure_seconds", 75.0),
            ("min_signal_quality", 0.0),
            ("publisher.endpoint", ""), ("publisher.auth_header", ""),
            ("publisher.timeout_sec", 5.0), ("publisher.max_retries", 3),
            ("publisher.dead_letter_path", "dead_letter"),
        ])
        g = lambda k: self.get_parameter(k).value
        return ScanConfig.from_dict({
            "api_key": g("api_key"), "offline": g("offline"),
            "measurement_preset": g("measurement_preset"),
            "precision_mode": g("precision_mode"),
            "camera_topic": g("camera_topic"), "submit_fps": g("submit_fps"),
            "enabled_triggers": list(g("enabled_triggers")),
            "acquire_face_timeout": g("acquire_face_timeout"),
            "max_measure_seconds": g("max_measure_seconds"),
            "min_signal_quality": g("min_signal_quality"),
            "publisher": {
                "endpoint": g("publisher.endpoint") or None,
                "auth_header": g("publisher.auth_header") or None,
                "timeout_sec": g("publisher.timeout_sec"),
                "max_retries": g("publisher.max_retries"),
                "dead_letter_path": g("publisher.dead_letter_path"),
            },
        })

def main(args=None):
    rclpy.init(args=args)
    node = ShenAiHealthScanNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.app.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":
    main()
