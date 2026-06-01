from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any


@dataclass
class PublisherConfig:
    endpoint: Optional[str] = None
    auth_header: Optional[str] = None
    timeout_sec: float = 5.0
    max_retries: int = 3
    dead_letter_path: str = "dead_letter"
    enable_fhir: bool = False

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "PublisherConfig":
        d = d or {}
        return cls(endpoint=d.get("endpoint"), auth_header=d.get("auth_header"),
                   timeout_sec=float(d.get("timeout_sec", 5.0)),
                   max_retries=int(d.get("max_retries", 3)),
                   dead_letter_path=d.get("dead_letter_path", "dead_letter"),
                   enable_fhir=bool(d.get("enable_fhir", False)))


@dataclass
class ScanConfig:
    api_key: str = ""
    offline: bool = False
    measurement_preset: str = "ONE_MINUTE_ALL_METRICS"
    precision_mode: str = "RELAXED"
    camera_topic: str = "/aima/hal/sensor/rgbd_head_front/rgb_image"
    camera_jpeg_scale: int = 2
    submit_fps: int = 30
    enabled_triggers: List[str] = field(default_factory=lambda: ["service"])
    acquire_face_timeout: float = 20.0
    max_measure_seconds: float = 75.0
    min_signal_quality: float = 0.0
    screen_static_video_dir: Optional[str] = None
    screen_result_video_dir: Optional[str] = None
    publisher: PublisherConfig = field(default_factory=PublisherConfig)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScanConfig":
        d = d or {}
        return cls(
            api_key=d.get("api_key", ""),
            offline=bool(d.get("offline", False)),
            measurement_preset=d.get("measurement_preset", "ONE_MINUTE_ALL_METRICS"),
            precision_mode=d.get("precision_mode", "RELAXED"),
            camera_topic=d.get("camera_topic", "/aima/hal/sensor/rgbd_head_front/rgb_image"),
            camera_jpeg_scale=int(d.get("camera_jpeg_scale", 2)),
            submit_fps=int(d.get("submit_fps", 30)),
            enabled_triggers=list(d.get("enabled_triggers", ["service"])),
            acquire_face_timeout=float(d.get("acquire_face_timeout", 20.0)),
            max_measure_seconds=float(d.get("max_measure_seconds", 75.0)),
            min_signal_quality=float(d.get("min_signal_quality", 0.0)),
            screen_static_video_dir=d.get("screen_static_video_dir") or None,
            screen_result_video_dir=d.get("screen_result_video_dir") or None,
            publisher=PublisherConfig.from_dict(d.get("publisher", {})),
        )
