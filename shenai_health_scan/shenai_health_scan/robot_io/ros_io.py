# robot_io/ros_io.py
from __future__ import annotations
import os, time, uuid
from typing import Dict, Any, Optional
from .cards import render_result_card

class RosIO:
    """Robot output via PlayTts + PlayVideo services. Best-effort, non-blocking-ish."""
    def __init__(self, node, card_dir: Optional[str] = None):
        from aimdk_msgs.srv import PlayTts, PlayVideo
        self._node = node
        self._card_dir = card_dir or os.path.join(os.path.expanduser("~"), "shenai_cards")
        os.makedirs(self._card_dir, exist_ok=True)
        self._tts = node.create_client(PlayTts, "/aimdk_5Fmsgs/srv/PlayTts")
        self._video = node.create_client(PlayVideo, "/face_ui_proxy/play_video")
        self._PlayTts = PlayTts
        self._PlayVideo = PlayVideo

    def speak(self, text: str, priority: int = 6) -> None:
        try:
            req = self._PlayTts.Request()
            req.tts_req.text = text
            req.tts_req.domain = "shenai_health_scan"
            req.tts_req.trace_id = "shenai"
            req.tts_req.is_interrupted = True
            req.tts_req.priority_weight = 0
            req.tts_req.priority_level.value = priority
            req.header.header.stamp = self._node.get_clock().now().to_msg()
            self._tts.call_async(req)
        except Exception as e:
            self._node.get_logger().warn(f"TTS failed: {e}")

    def show(self, view: str, data: Dict[str, Any]) -> None:
        try:
            if view == "result_card" and "vitals" in data:
                png = render_result_card(data["vitals"])
                path = os.path.join(self._card_dir, f"card_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}.png")
                with open(path, "wb") as f:
                    f.write(png)
                self._play_video(path, mode=1, priority=5)
            # Other views (coaching/measuring/idle/error) can map to preset media
            # files configured on the robot; left as best-effort no-ops for MVP.
        except Exception as e:
            self._node.get_logger().warn(f"show({view}) failed: {e}")

    def _play_video(self, path: str, mode: int, priority: int):
        req = self._PlayVideo.Request()
        req.video_path = path
        req.mode = mode
        req.priority = priority
        req.header.header.stamp = self._node.get_clock().now().to_msg()
        self._video.call_async(req)
