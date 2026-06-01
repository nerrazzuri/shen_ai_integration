# camera/ros_camera.py
from __future__ import annotations
import threading, time
from typing import Optional, Tuple

class RosCamera:
    """ROS 2 subscriber -> latest BGR frame. Construct with a live rclpy Node.

    Subscribes to a raw sensor_msgs/Image, or a sensor_msgs/CompressedImage when
    the topic ends with "/compressed" (the X2 publishes the full-rate stream there).
    """
    def __init__(self, node, topic: str):
        from sensor_msgs.msg import Image, CompressedImage
        from cv_bridge import CvBridge
        from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
        import cv2
        self._cv2 = cv2
        self._bridge = CvBridge()
        self._lock = threading.Lock()
        self._latest: Optional[Tuple[bytes, int, int, int, int]] = None
        self._count = 0
        self._t0 = time.time()
        qos = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT,
                         history=QoSHistoryPolicy.KEEP_LAST, depth=5)
        if topic.endswith("/compressed"):
            self._sub = node.create_subscription(CompressedImage, topic, self._cb_compressed, qos)
        else:
            self._sub = node.create_subscription(Image, topic, self._cb, qos)
        node.get_logger().info(f"RosCamera subscribed to {topic}")

    def _store(self, img):
        h, w = img.shape[:2]
        with self._lock:
            self._latest = (img.tobytes(), w, h, w * 3, time.monotonic_ns())
            self._count += 1

    def _cb(self, msg):
        img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
        enc = msg.encoding.lower()
        if enc == "rgb8":
            img = self._cv2.cvtColor(img, self._cv2.COLOR_RGB2BGR)
        elif enc == "mono8":
            img = self._cv2.cvtColor(img, self._cv2.COLOR_GRAY2BGR)
        self._store(img)

    def _cb_compressed(self, msg):
        # cv_bridge decodes JPEG/PNG and returns BGR directly with desired_encoding="bgr8"
        img = self._bridge.compressed_imgmsg_to_cv2(msg, desired_encoding="bgr8")
        self._store(img)

    def start(self): pass
    def stop(self): pass
    def get_latest(self):
        with self._lock:
            return self._latest

    @property
    def measured_fps(self) -> float:
        dt = time.time() - self._t0
        return self._count / dt if dt > 0 else 0.0
