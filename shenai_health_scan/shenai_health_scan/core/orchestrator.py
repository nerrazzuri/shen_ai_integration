from __future__ import annotations
import threading
from typing import List, Optional
from .types import (
    ScanState, FaceHint, EnginePoll, Vitals,
    Speak, ShowScreen, EngineCmd, PublishResults,
)

Effect = object  # union of Speak/ShowScreen/EngineCmd/PublishResults

_HINT_SPEECH = {
    FaceHint.NO_FACE: "Please stand in front of me and look at my eyes.",
    FaceHint.TOO_FAR: "Come a little closer, please.",
    FaceHint.TOO_CLOSE: "You are too close. Please move back a little.",
    FaceHint.OFF_CENTER: "Center your face, please.",
    FaceHint.HOLD_STILL: "Hold still, please.",
    FaceHint.READY: "Good, stay there.",
}


class ScanOrchestrator:
    def __init__(self, acquire_face_timeout: float = 20.0,
                 max_measure_seconds: float = 75.0, min_signal_quality: float = 0.0):
        self.state = ScanState.IDLE
        self._acquire_timeout = acquire_face_timeout
        self._max_measure = max_measure_seconds
        self._min_quality = min_signal_quality
        self._lock = threading.Lock()
        self._scan_requested = False
        self._state_entered_at = 0.0
        self._last_hint: Optional[FaceHint] = None
        self._last_hold_prompt_at: Optional[float] = None

    def request_scan(self) -> None:
        with self._lock:
            self._scan_requested = True

    def _consume_request(self) -> bool:
        with self._lock:
            if self._scan_requested:
                self._scan_requested = False
                return True
            return False

    def _enter(self, state: ScanState, now: float) -> None:
        self.state = state
        self._state_entered_at = now
        self._last_hint = None
        self._last_hold_prompt_at = now if state == ScanState.MEASURING else None

    def on_tick(self, poll: EnginePoll, now: float) -> List[Effect]:
        if self.state in (ScanState.IDLE, ScanState.DONE, ScanState.FAILED):
            if self._consume_request():
                self._enter(ScanState.ACQUIRE_FACE, now)
                return [EngineCmd("reset"), ShowScreen("coaching", {}),
                        Speak("Let's check your vitals. Please look at my eyes.")]
            return []

        if self.state == ScanState.ACQUIRE_FACE:
            effects: List[Effect] = []
            if poll.is_ready:
                self._enter(ScanState.MEASURING, now)
                return [EngineCmd("start"), ShowScreen("measuring", {}),
                        Speak("Measuring now. Please hold still.")]
            if now - self._state_entered_at > self._acquire_timeout:
                self._enter(ScanState.FAILED, now)
                return [EngineCmd("stop"), ShowScreen("error", {}),
                        Speak("I couldn't get a clear view of your face. Let's try again later.")]
            if poll.face_hint != FaceHint.NONE and poll.face_hint != self._last_hint:
                self._last_hint = poll.face_hint
                effects.append(Speak(_HINT_SPEECH.get(poll.face_hint, "")))
            return effects

        if self.state == ScanState.MEASURING:
            if poll.finished and poll.vitals is not None:
                if poll.signal_quality < self._min_quality:
                    self._enter(ScanState.FAILED, now)
                    return [EngineCmd("stop"), ShowScreen("error", {}),
                            Speak("I couldn't get a clear enough reading. Let's try again later.")]
                self._enter(ScanState.DONE, now)
                return [ShowScreen("processing_results", {}),
                        Speak("Scan complete. Please wait while I prepare your results."),
                        ShowScreen("result_card", {"vitals": poll.vitals.to_dict()}),
                        Speak(self._summary_speech(poll.vitals)),
                        PublishResults({"vitals": poll.vitals.to_dict(),
                                        "quality": {"average_signal_quality": poll.signal_quality,
                                                    "bad_signal_seconds": poll.bad_signal_seconds}})]
            if poll.failed or (now - self._state_entered_at > self._max_measure):
                self._enter(ScanState.FAILED, now)
                return [EngineCmd("stop"), ShowScreen("error", {}),
                        Speak("I couldn't complete the reading. Let's try again later.")]
            effects: List[Effect] = [ShowScreen("measuring", {"progress": poll.progress})]
            if self._last_hold_prompt_at is None or now - self._last_hold_prompt_at >= 3.0:
                self._last_hold_prompt_at = now
                effects.append(Speak("Hold your position until scanning is complete."))
            return effects

        return []

    @staticmethod
    def _summary_speech(v: Vitals) -> str:
        parts = []
        if v.heart_rate_bpm is not None:
            parts.append(f"your heart rate is {int(round(v.heart_rate_bpm))} beats per minute")
        if v.systolic_bp_mmhg is not None and v.diastolic_bp_mmhg is not None:
            parts.append(f"blood pressure {int(round(v.systolic_bp_mmhg))} over {int(round(v.diastolic_bp_mmhg))}")
        body = ", ".join(parts) if parts else "your results are ready"
        return f"All done. {body}."
