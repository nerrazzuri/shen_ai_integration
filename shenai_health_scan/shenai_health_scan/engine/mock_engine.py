from __future__ import annotations
from typing import Optional
from ..core.types import EnginePoll, Vitals, FaceHint


class MockEngine:
    def __init__(self, face_after=15, ready_after=45, finish_after=300):
        self._face_after = face_after
        self._ready_after = ready_after
        self._finish_after = finish_after
        self._n = 0
        self._started = False

    def begin_session(self): self._n = 0; self._started = False
    def start(self): self._started = True
    def stop(self): self._started = False
    def submit(self, data, width, height, stride, ts_ns): self._n += 1
    def close(self): pass

    def poll(self) -> EnginePoll:
        face = self._n > self._face_after
        ready = self._n > self._ready_after
        finished = self._started and self._n > self._finish_after
        if not face:
            hint = FaceHint.NO_FACE
        elif not ready:
            hint = FaceHint.HOLD_STILL
        else:
            hint = FaceHint.READY
        progress = 0.0
        if self._started and self._finish_after > self._ready_after:
            progress = max(0.0, min(1.0, (self._n - self._ready_after) /
                                    (self._finish_after - self._ready_after)))
        return EnginePoll(face_present=face, is_ready=ready, progress=progress,
                          finished=finished, signal_quality=0.9,
                          face_hint=hint, vitals=self._vitals() if finished else None)

    @staticmethod
    def _vitals() -> Vitals:
        return Vitals(heart_rate_bpm=72, hrv_sdnn_ms=45, breathing_rate_bpm=15,
                      stress_index=1.8, systolic_bp_mmhg=120, diastolic_bp_mmhg=80)

    def final_results(self) -> Optional[Vitals]:
        return self._vitals()

    def measurement_id(self): return "mock-measurement"
    def trace_id(self): return "mock-trace"
