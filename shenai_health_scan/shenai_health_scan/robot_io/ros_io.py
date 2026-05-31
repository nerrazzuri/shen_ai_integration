# robot_io/ros_io.py
from __future__ import annotations
import os
from typing import Dict, Any, Optional
from .video_presenter import VideoScreenPresenter
from .videos import VideoAssetManager

class RosIO:
    """Robot output via PlayTts + PlayVideo services. Best-effort, non-blocking-ish."""
    def __init__(self, node, card_dir: Optional[str] = None,
                 static_video_dir: Optional[str] = None,
                 result_video_dir: Optional[str] = None):
        from aimdk_msgs.srv import PlayTts, PlayVideo
        self._node = node
        self._card_dir = card_dir or os.path.join(os.path.expanduser("~"), "shenai_cards")
        os.makedirs(self._card_dir, exist_ok=True)
        self._tts = node.create_client(PlayTts, "/aimdk_5Fmsgs/srv/PlayTts")
        self._video = node.create_client(PlayVideo, "/face_ui_proxy/play_video")
        self._PlayTts = PlayTts
        self._PlayVideo = PlayVideo
        video_dir = static_video_dir or os.path.join(self._card_dir, "videos")
        result_dir = result_video_dir or os.path.join(self._card_dir, "videos")
        self._video_assets = VideoAssetManager(
            video_dir, generate_missing_static=static_video_dir is None,
            result_root=result_dir)
        if static_video_dir is None:
            try:
                self._video_assets.ensure_static_videos()
            except Exception as e:
                self._node.get_logger().warn(f"Video asset generation failed: {e}")
        self._video_presenter = VideoScreenPresenter(
            self._video_assets,
            lambda path, loop: self._play_video(path, mode=2 if loop else 1, priority=5),
        )

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
            self._video_presenter.show(view, data)
        except Exception as e:
            self._node.get_logger().warn(f"show({view}) failed: {e}")

    def _play_video(self, path: str, mode: int, priority: int):
        req = self._PlayVideo.Request()
        req.video_path = path
        req.mode = mode
        req.priority = priority
        req.header.header.stamp = self._node.get_clock().now().to_msg()
        self._video.call_async(req)
