from __future__ import annotations
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional, Any, Dict


class ScanState(str, Enum):
    IDLE = "idle"
    TRIGGERED = "triggered"
    ACQUIRE_FACE = "acquire_face"
    MEASURING = "measuring"
    DONE = "done"
    FAILED = "failed"


class FaceHint(str, Enum):
    NONE = "none"
    NO_FACE = "no_face"
    TOO_FAR = "too_far"
    TOO_CLOSE = "too_close"
    OFF_CENTER = "off_center"
    HOLD_STILL = "hold_still"
    READY = "ready"


@dataclass
class Vitals:
    heart_rate_bpm: Optional[float] = None
    hrv_sdnn_ms: Optional[float] = None
    breathing_rate_bpm: Optional[float] = None
    stress_index: Optional[float] = None
    systolic_bp_mmhg: Optional[float] = None
    diastolic_bp_mmhg: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        return {k: v for k, v in self.__dict__.items() if v is not None}


@dataclass
class EnginePoll:
    face_present: bool
    is_ready: bool = False
    progress: float = 0.0
    finished: bool = False
    failed: bool = False
    signal_quality: float = 0.0
    bad_signal_seconds: float = 0.0
    face_hint: FaceHint = FaceHint.NONE
    vitals: Optional[Vitals] = None


@dataclass
class ResultPayload:
    measurement_id: str
    trace_id: str
    timestamp: str
    vitals: Dict[str, Any]
    quality: Dict[str, Any]
    health_risks: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        d = {"measurement_id": self.measurement_id, "trace_id": self.trace_id,
             "timestamp": self.timestamp, "vitals": self.vitals, "quality": self.quality}
        if self.health_risks is not None:
            d["health_risks"] = self.health_risks
        return d


# --- Effects (typed intents emitted by the orchestrator) ---
@dataclass
class Speak:
    text: str

@dataclass
class ShowScreen:
    view: str
    data: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EngineCmd:
    cmd: str  # "start" | "stop" | "reset"

@dataclass
class PublishResults:
    payload: Dict[str, Any]
