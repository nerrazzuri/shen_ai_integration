from __future__ import annotations

import time
from typing import Callable, Optional


def _fmt_bbox(bbox):
    if not bbox:
        return "bbox=None"
    cx = bbox["x"] + bbox["width"] / 2.0
    cy = bbox["y"] + bbox["height"] / 2.0
    return f"bbox=(cx={cx:.2f}, cy={cy:.2f}, w={bbox['width']:.2f}, h={bbox['height']:.2f})"


def _fmt_pose(pose):
    if not pose:
        return "pose=None"
    return (
        "pose=("
        f"yaw={pose['yaw']:.1f}, pitch={pose['pitch']:.1f}, roll={pose['roll']:.1f}"
        ")"
    )


class DebugEngineProxy:
    def __init__(
        self,
        engine,
        emit: Callable[[str], None] = print,
        now: Callable[[], float] = time.monotonic,
        camera_fps: Optional[Callable[[], float]] = None,
        interval_sec: float = 1.0,
    ):
        self._engine = engine
        self._emit = emit
        self._now = now
        self._camera_fps = camera_fps
        self._interval = interval_sec
        self._next_emit_at = 0.0

    def __getattr__(self, name):
        return getattr(self._engine, name)

    def poll(self):
        poll = self._engine.poll()
        now = self._now()
        if now >= self._next_emit_at:
            self._next_emit_at = now + self._interval
            self._emit(self._format_status(poll))
        return poll

    def _format_status(self, poll) -> str:
        status = {}
        debug_status = getattr(self._engine, "debug_status", None)
        if debug_status is not None:
            try:
                status = debug_status()
            except Exception as e:
                status = {"debug_error": str(e)}

        fps = self._camera_fps() if self._camera_fps is not None else None
        parts = [
            "[DEBUG]",
            f"face_state={status.get('face_state', '?')}",
            f"measurement_state={status.get('measurement_state', '?')}",
            f"ready={status.get('ready', poll.is_ready)}",
            f"vitals={'present' if poll.vitals is not None else 'missing'}",
            f"progress={poll.progress:.2f}",
            f"quality={poll.signal_quality:.2f}",
            _fmt_bbox(status.get("bbox")),
            _fmt_pose(status.get("pose")),
        ]
        if fps is not None:
            parts.append(f"camera_fps={fps:.1f}")
        if "debug_error" in status:
            parts.append(f"debug_error={status['debug_error']}")
        return " ".join(parts)
