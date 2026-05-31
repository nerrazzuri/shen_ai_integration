# camera/fake_camera.py
from __future__ import annotations
import threading, time
from typing import Optional, Tuple, Union
import cv2

class FakeCamera:
    """Replays a video file (loops) or webcam index as BGR frames."""
    def __init__(self, source: Union[str, int] = 0, fps: float = 30.0):
        self._source = source
        self._fps = fps
        self._cap: Optional[cv2.VideoCapture] = None
        self._lock = threading.Lock()
        self._latest: Optional[Tuple[bytes, int, int, int, int]] = None
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()
        self._count = 0
        self._t0 = 0.0

    def start(self):
        self._cap = cv2.VideoCapture(self._source)
        self._stop.clear(); self._t0 = time.time(); self._count = 0
        self._thread = threading.Thread(target=self._run, daemon=True); self._thread.start()

    def _run(self):
        period = 1.0 / self._fps
        while not self._stop.is_set():
            ok, frame = self._cap.read()
            if not ok:
                if isinstance(self._source, str):
                    self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0); continue
                break
            h, w = frame.shape[:2]
            data = frame.tobytes()  # already BGR from cv2
            with self._lock:
                self._latest = (data, w, h, w * 3, time.monotonic_ns())
                self._count += 1
            time.sleep(period)

    def get_latest(self):
        with self._lock:
            return self._latest

    @property
    def measured_fps(self) -> float:
        dt = time.time() - self._t0
        return self._count / dt if dt > 0 else 0.0

    def stop(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=2.0)
        if self._cap: self._cap.release()
