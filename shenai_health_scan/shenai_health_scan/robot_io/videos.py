from __future__ import annotations

import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, Optional

import cv2
import numpy as np

_LABELS = [
    ("heart_rate_bpm", "Heart Rate", "bpm"),
    ("hrv_sdnn_ms", "HRV", "ms"),
    ("breathing_rate_bpm", "Breathing", "/min"),
    ("stress_index", "Stress", ""),
    ("systolic_bp_mmhg", "BP Systolic", "mmHg"),
    ("diastolic_bp_mmhg", "BP Diastolic", "mmHg"),
]


def progress_bucket(progress: float) -> Optional[int]:
    pct = max(0, min(100, int(progress * 100)))
    bucket = (pct // 10) * 10
    return bucket if bucket >= 10 else None


def _put_centered_text(img, text: str, y: int, scale: float, color, thickness: int = 2):
    size, _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, scale, thickness)
    x = max(0, (img.shape[1] - size[0]) // 2)
    cv2.putText(img, text, (x, y), cv2.FONT_HERSHEY_SIMPLEX,
                scale, color, thickness, cv2.LINE_AA)


def _base_frame(width: int, height: int):
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (24, 28, 32)
    cv2.rectangle(img, (0, 0), (width, height), (35, 42, 50), 24)
    return img


def _draw_progress(img, percent: int):
    width, height = img.shape[1], img.shape[0]
    _put_centered_text(img, "Health Scan", int(height * 0.22), 1.6, (255, 255, 255), 3)
    _put_centered_text(img, f"{percent}% Complete", int(height * 0.40), 1.35,
                       (120, 230, 170), 3)
    bar_w = int(width * 0.66)
    bar_h = 34
    x0 = (width - bar_w) // 2
    y0 = int(height * 0.55)
    cv2.rectangle(img, (x0, y0), (x0 + bar_w, y0 + bar_h), (80, 88, 96), -1)
    cv2.rectangle(img, (x0, y0), (x0 + int(bar_w * percent / 100), y0 + bar_h),
                  (80, 210, 145), -1)
    _put_centered_text(img, "Please hold still", int(height * 0.76), 1.0,
                       (220, 230, 235), 2)


def _draw_processing(img):
    height = img.shape[0]
    _put_centered_text(img, "Scan Complete", int(height * 0.34), 1.5,
                       (255, 255, 255), 3)
    _put_centered_text(img, "Preparing your results", int(height * 0.53), 1.15,
                       (120, 230, 170), 2)


def _draw_result(img, vitals: Dict[str, Any]):
    width, height = img.shape[1], img.shape[0]
    cv2.putText(img, "Health Scan Results", (60, 95),
                cv2.FONT_HERSHEY_SIMPLEX, 1.45, (255, 255, 255), 3, cv2.LINE_AA)
    y = 185
    for key, label, unit in _LABELS:
        value = vitals.get(key)
        if value is None:
            continue
        text = f"{label}: {float(value):.0f} {unit}".strip()
        cv2.putText(img, text, (80, y), cv2.FONT_HERSHEY_SIMPLEX, 1.0,
                    (120, 230, 170), 2, cv2.LINE_AA)
        y += 68
    cv2.rectangle(img, (width - 340, height - 92), (width - 60, height - 44),
                  (80, 210, 145), -1)
    cv2.putText(img, "Complete", (width - 300, height - 57),
                cv2.FONT_HERSHEY_SIMPLEX, 0.9, (20, 28, 32), 2, cv2.LINE_AA)


def _write_video(path: Path, draw, width: int, height: int,
                 fps: int, duration_sec: float) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(str(path), fourcc, float(fps), (width, height))
    if not writer.isOpened():
        raise RuntimeError(f"Could not open video writer for {path}")
    try:
        frames = max(1, int(fps * duration_sec))
        for _ in range(frames):
            img = _base_frame(width, height)
            draw(img)
            writer.write(img)
    finally:
        writer.release()
    if not path.exists() or path.stat().st_size == 0:
        raise RuntimeError(f"Video writer did not create {path}")
    return str(path)


class VideoAssetManager:
    def __init__(self, root: os.PathLike | str, width: int = 1280, height: int = 720,
                 fps: int = 24, duration_sec: float = 2.0,
                 generate_missing_static: bool = True,
                 result_root: os.PathLike | str | None = None):
        self.root = Path(root)
        self.result_root = Path(result_root) if result_root is not None else self.root
        self.width = width
        self.height = height
        self.fps = fps
        self.duration_sec = duration_sec
        self.generate_missing_static = generate_missing_static

    def progress_video_path(self, percent: int) -> str:
        if percent < 10 or percent > 100 or percent % 10 != 0:
            raise ValueError("progress video percent must be 10, 20, ... 100")
        path = self.root / f"progress_{percent}.mp4"
        if self.generate_missing_static and not path.exists():
            _write_video(path, lambda img: _draw_progress(img, percent),
                         self.width, self.height, self.fps, self.duration_sec)
        return str(path)

    def processing_video_path(self) -> str:
        path = self.root / "processing_result.mp4"
        if self.generate_missing_static and not path.exists():
            _write_video(path, _draw_processing, self.width, self.height,
                         self.fps, self.duration_sec)
        return str(path)

    def ensure_static_videos(self):
        paths = [self.progress_video_path(percent) for percent in range(10, 101, 10)]
        paths.append(self.processing_video_path())
        return paths

    def result_video_path(self, vitals: Dict[str, Any]) -> str:
        name = f"result_{int(time.time() * 1000)}_{uuid.uuid4().hex[:6]}.mp4"
        path = self.result_root / name
        return _write_video(path, lambda img: _draw_result(img, vitals),
                            self.width, self.height, self.fps, self.duration_sec)
