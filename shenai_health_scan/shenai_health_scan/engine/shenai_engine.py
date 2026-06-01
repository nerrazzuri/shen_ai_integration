# engine/shenai_engine.py
from __future__ import annotations
from typing import Optional
from ..core.types import EnginePoll, Vitals, FaceHint
from ..core.config import ScanConfig


class ShenAiEngine:
    """Wraps the Shen.AI headless Python SDK. The only owner of the SDK context."""
    def __init__(self, config: ScanConfig):
        import uuid
        from shenai_sdk import (
            ShenaiSDK, MeasurementPreset, PrecisionMode, MeasurementState, FaceState,
        )
        self._MeasurementState = MeasurementState
        self._FaceState = FaceState
        # A valid user_id (UUID) is required for the SDK's measurement telemetry;
        # without it the engine logs "Report measurement started failed: invalid UUID length: 0".
        self._sdk = ShenaiSDK(api_key=config.api_key, user_id=str(uuid.uuid4()),
                              offline=config.offline)
        self._sdk.precision_mode = getattr(PrecisionMode, config.precision_mode)
        self._sdk.measurement_preset = getattr(MeasurementPreset, config.measurement_preset)
        # Shen.AI indexes frames by timestamp and expects a uniform >= 30 fps cadence.
        # The camera arrives with jitter, which leaves gaps/collisions in the SDK's
        # frame ids -> "texture jitter buffer overflow ... skipping ahead" and a dead
        # signal. Submit with a uniform synthetic cadence so frame ids stay contiguous.
        self._frame_period_ns = int(1_000_000_000 / max(1, config.submit_fps))
        self._frame_idx = 0

    def begin_session(self):
        self._frame_idx = 0
        self._sdk.reset_measurement_session()
    def start(self): self._sdk.start_measurement()
    def stop(self): self._sdk.stop_measurement()

    def submit(self, data, width, height, stride, ts_ns):
        # ts_ns (real camera arrival time) is ignored on purpose: the SDK wants
        # uniform spacing, so we clock frames at the configured submit_fps.
        self._sdk.submit_frame(data, width=width, height=height, stride_bytes=stride,
                               timestamp_ns=self._frame_idx * self._frame_period_ns)
        self._frame_idx += 1

    def poll(self) -> EnginePoll:
        face_state = self._sdk.get_face_state()
        face_present = face_state != self._FaceState.NOT_VISIBLE
        is_ready = self._sdk.is_ready_to_start_measurement()
        progress = self._sdk.get_progress_percent() / 100.0
        mstate = self._sdk.get_measurement_state()
        finished = mstate == self._MeasurementState.FINISHED
        failed = mstate == self._MeasurementState.FAILED
        sq = self._sdk.get_current_signal_quality_metric()
        bad = self._sdk.get_total_bad_signal_seconds()
        vitals = self._final_vitals() if finished else None
        return EnginePoll(face_present=face_present, is_ready=is_ready, progress=progress,
                          finished=finished, failed=failed, signal_quality=sq,
                          bad_signal_seconds=bad,
                          face_hint=self._hint(face_state, is_ready), vitals=vitals)

    def _hint(self, face_state, is_ready) -> FaceHint:
        FS = self._FaceState
        if face_state == FS.NOT_VISIBLE:
            return FaceHint.NO_FACE
        if face_state == FS.TOO_FAR:
            return FaceHint.TOO_FAR
        if face_state == FS.TOO_CLOSE:
            return FaceHint.TOO_CLOSE
        if face_state in (FS.NOT_CENTERED, FS.TURNED_AWAY):
            return FaceHint.OFF_CENTER
        if is_ready:
            return FaceHint.READY
        return FaceHint.HOLD_STILL

    def _final_vitals(self) -> Optional[Vitals]:
        r = self._sdk.get_measurement_results()
        if r is None:
            return None
        return Vitals(heart_rate_bpm=r.heart_rate_bpm, hrv_sdnn_ms=r.hrv_sdnn_ms,
                      breathing_rate_bpm=r.breathing_rate_bpm, stress_index=r.stress_index,
                      systolic_bp_mmhg=r.systolic_bp_mmhg, diastolic_bp_mmhg=r.diastolic_bp_mmhg)

    def final_results(self) -> Optional[Vitals]:
        return self._final_vitals()

    def measurement_id(self) -> str:
        return self._sdk.get_measurement_id()

    def trace_id(self) -> str:
        return self._sdk.get_trace_id()

    def debug_status(self) -> dict:
        bbox = self._sdk.get_face_bbox()
        pose = self._sdk.get_face_pose()
        return {
            "face_state": self._sdk.get_face_state().name,
            "measurement_state": self._sdk.get_measurement_state().name,
            "ready": self._sdk.is_ready_to_start_measurement(),
            "bbox": None if bbox is None else {
                "x": bbox.x, "y": bbox.y,
                "width": bbox.width, "height": bbox.height,
            },
            "pose": None if pose is None else {
                "yaw": pose.rotation.yaw,
                "pitch": pose.rotation.pitch,
                "roll": pose.rotation.roll,
            },
        }

    def close(self):
        self._sdk.close()
        self._sdk.destroy_runtime()
