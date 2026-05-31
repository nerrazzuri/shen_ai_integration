# Shen.AI Health Scan on AgiBot X2 — MVP Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a runnable MVP ROS 2 Python node that runs a guided facial rPPG health scan from the AgiBot X2 camera via the Shen.AI headless Python SDK, shows vitals on the face screen, speaks guidance via TTS, and POSTs the full result payload to a third-party API — plus an off-robot demo mode (webcam + mock engine) that runs on a dev laptop.

**Architecture:** Approach B from the design spec — one in-process ROS 2 Python node, internally decomposed into focused components (CameraSource, ShenAiEngine, ScanOrchestrator, RobotIO, ResultsPublisher) plus a pluggable ScanTrigger layer. Three threads (camera callback / fixed-rate measurement loop / publisher worker) keep rPPG frame timing clean. All hardware/SDK code sits behind interfaces so the pure core is unit-testable and the pipeline runs off-robot with fakes.

**Tech Stack:** Python 3.10+, ROS 2 Humble (`rclpy`, `cv_bridge`, `sensor_msgs`, `aimdk_msgs`), Shen.AI headless Python SDK (`shenai_sdk` ctypes wrapper + `libShenaiSDK.so`), OpenCV (`cv2`), `numpy`, `requests`, `pytest`.

**Design spec:** `docs/superpowers/specs/2026-05-31-shenai-x2-integration-design.md` (read it first).

---

## Environment notes (read before starting)

| Concern | Dev workstation (Ubuntu 22.04 x86_64) | Robot PC2 (Jetson Orin NX, arm64) |
|---|---|---|
| Shen.AI SDK | **x64** headless Python build (download from developer.shen.ai) | **arm64** build (`shenai-sdk-python-linux-arm64`, already have) |
| ROS 2 | Humble (matches robot) — needed only for ROS adapters/integration tests | Humble (pre-installed on robot) |
| What runs here | pure core tests, publisher tests, card render, **demo mode** (webcam + mock or real x64 engine) | full ROS 2 node with real camera/TTS/face-screen |

- The `.so` is architecture-specific: the arm64 build will NOT load on x86_64. Get the x64 build for the workstation.
- Vendor SDKs are git-ignored. Place `shenai_sdk/` on `PYTHONPATH` or set `SHENAI_SDK_LIB`.
- `aimdk_msgs` comes from the X2 SDK (`lx2501_3-v0.9.0.4/src/aimdk_msgs`); build it into your ROS 2 workspace to get `aimdk_msgs.srv`/`.msg` for the ROS adapters and integration tests.

## Verified interface facts (from the SDK packages — do not re-derive)

- **Shen.AI** (`shenai_sdk/client.py`): `ShenaiSDK(api_key, user_id=None, offline=True, language="auto")`; `.precision_mode`, `.measurement_preset`, `set_custom_measurement_config(...)`; `start_measurement()`, `stop_measurement()`, `reset_measurement_session()`; `submit_frame(data, width, height, stride_bytes=None, timestamp_ns=-1, pixel_format=PixelFormat.BGR24)`; `get_face_state()`, `is_ready_to_start_measurement()`, `get_progress_percent()`, `get_measurement_state()`, `get_realtime_metrics(period_sec)`, `get_measurement_results()`, `get_health_risks()`, `get_current_signal_quality_metric()`, `get_total_bad_signal_seconds()`, `get_measurement_id()`, `get_trace_id()`, `close()`, `destroy_runtime()`. Enums: `MeasurementState`, `FaceState`, `PrecisionMode`, `MeasurementPreset`, `PixelFormat`. `MeasurementResults` fields: `heart_rate_bpm`, `hrv_sdnn_ms`, `breathing_rate_bpm`, `stress_index`, `systolic_bp_mmhg`, `diastolic_bp_mmhg`, `average_signal_quality`, etc.
- **X2 camera**: topic `/aima/hal/sensor/rgbd_head_front/rgb_image` (`sensor_msgs/Image`, `rgb8`); convert with `cv_bridge.imgmsg_to_cv2(msg, 'passthrough')` then `cv2.cvtColor(img, cv2.COLOR_RGB2BGR)` (see `take_photo.py`). QoS: `BEST_EFFORT`, `KEEP_LAST`, depth 5.
- **X2 TTS**: srv `aimdk_msgs/srv/PlayTts` on `/aimdk_5Fmsgs/srv/PlayTts`. Fill `req.tts_req.text`, `.domain`, `.trace_id`, `.is_interrupted=True`, `.priority_weight=0`, `.priority_level.value=6` (INTERACTION_L6); set `req.header.header.stamp`. Response `resp.tts_resp.is_success`.
- **X2 face screen**: srv `aimdk_msgs/srv/PlayVideo` on `/face_ui_proxy/play_video`. Fill `req.video_path`, `req.mode` (1=once, 2=loop), `req.priority`; set `req.header.header.stamp`. Response `resp.success`, `resp.message`.
- **X2 touch**: topic `/aima/hal/sensor/touch_head` (`aimdk_msgs/msg/TouchState`); event constants `PAT_ONCE`, `PAT_TWICE`, `PAT_TRIPLE`, etc. on `msg.event_type`.

---

## File structure

ROS 2 `ament_python` package `shenai_health_scan`, placed beside `py_examples` in the X2 workspace `src/`.

```
shenai_health_scan/
  package.xml                       # ament_python; deps: rclpy sensor_msgs cv_bridge aimdk_msgs
  setup.py                          # entry points: node, demo
  setup.cfg
  resource/shenai_health_scan
  config/params.yaml                # all runtime config
  launch/shenai_health_scan.launch.py
  shenai_health_scan/
    __init__.py
    core/
      __init__.py
      types.py          # enums + dataclasses: ScanState, FaceHint, EnginePoll, Vitals, ResultPayload, Effect types
      orchestrator.py   # ScanOrchestrator — pure state machine, on_tick() -> [Effect]
      config.py         # ScanConfig dataclass + from_dict()
    engine/
      __init__.py
      base.py           # EngineBase (Protocol): begin_session/start/stop/submit/poll/final_results/close
      mock_engine.py    # MockEngine — deterministic simulated scan (no SDK)
      shenai_engine.py  # ShenAiEngine — wraps shenai_sdk (lazy import)
    camera/
      __init__.py
      base.py           # CameraSource (Protocol): start/stop/get_latest/measured_fps
      fake_camera.py    # FakeCamera — webcam/video file via cv2
      ros_camera.py     # RosCamera — rclpy subscriber + cv_bridge (lazy import)
    robot_io/
      __init__.py
      base.py           # RobotIO (Protocol): speak/show
      console_io.py     # ConsoleIO — prints (demo/tests)
      cards.py          # render_result_card(vitals) -> png bytes / mp4 path (cv2)
      ros_io.py         # RosIO — PlayTts + PlayVideo (lazy import)
    publisher/
      __init__.py
      results_publisher.py  # ResultsPublisher — threaded queue -> requests POST -> dead-letter
    triggers/
      __init__.py
      base.py           # ScanTrigger (Protocol): start(on_trigger)/stop
      manual_trigger.py # ManualTrigger — programmatic (demo/tests)
      service_trigger.py# ServiceTrigger — ROS ~/start_scan (lazy)
      touch_trigger.py  # TouchTrigger — ROS touch_head topic (lazy)
      topic_trigger.py  # TopicTrigger — generic ROS std_msgs/Empty topic (lazy)
    loop.py             # MeasurementLoop — fixed-rate thread: camera->engine->orchestrator->effects
    runner.py           # ScanApp — wires components, owns loop + publisher + triggers (framework-agnostic)
    demo.py             # off-robot entrypoint: FakeCamera + (Mock|ShenAi) engine + ConsoleIO + ManualTrigger
    node.py             # ROS 2 entrypoint: RosCamera + ShenAiEngine + RosIO + ROS triggers
  tests/
    __init__.py
    test_types.py
    test_orchestrator.py
    test_config.py
    test_mock_engine.py
    test_results_publisher.py
    test_cards.py
    test_loop.py
    test_runner_demo.py
```

**Layering rule:** `core/`, `engine/mock_engine.py`, `engine/base.py`, `camera/base.py`, `camera/fake_camera.py`, `robot_io/base.py`, `robot_io/console_io.py`, `robot_io/cards.py`, `publisher/`, `triggers/base.py`, `triggers/manual_trigger.py`, `loop.py`, `runner.py`, `demo.py` import **no ROS and no SDK at module top-level** → fully runnable/tested on the workstation. ROS/SDK live only in `*ros*.py`, `shenai_engine.py`, and `node.py`, imported lazily.

---

## Phase 0 — Scaffolding

### Task 0: Create package skeleton + pytest config

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/__init__.py` (empty)
- Create: `shenai_health_scan/tests/__init__.py` (empty)
- Create: `shenai_health_scan/pytest.ini`
- Create: all `core/__init__.py`, `engine/__init__.py`, etc. (empty package markers)

- [ ] **Step 1: Create dirs and empty `__init__.py` files** for every subpackage listed in the file structure.

- [ ] **Step 2: Create `pytest.ini`**

```ini
[pytest]
testpaths = tests
python_files = test_*.py
addopts = -v
```

- [ ] **Step 3: Verify pytest collects nothing yet**

Run: `cd shenai_health_scan && python -m pytest`
Expected: "no tests ran" (exit 5) — confirms layout is importable.

- [ ] **Step 4: Commit**

```bash
git add shenai_health_scan
git commit -m "chore: scaffold shenai_health_scan package"
```

---

## Phase 1 — Core types + state machine (pure, full TDD)

### Task 1: Core types

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/core/types.py`
- Test: `shenai_health_scan/tests/test_types.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_types.py
from shenai_health_scan.core.types import (
    ScanState, FaceHint, EnginePoll, Vitals, ResultPayload,
    Speak, ShowScreen, EngineCmd, PublishResults,
)

def test_vitals_to_dict_drops_none():
    v = Vitals(heart_rate_bpm=72, hrv_sdnn_ms=None, breathing_rate_bpm=15,
               stress_index=None, systolic_bp_mmhg=120, diastolic_bp_mmhg=80)
    d = v.to_dict()
    assert d == {"heart_rate_bpm": 72, "breathing_rate_bpm": 15,
                 "systolic_bp_mmhg": 120, "diastolic_bp_mmhg": 80}

def test_enginepoll_defaults():
    p = EnginePoll(face_present=False)
    assert p.is_ready is False and p.progress == 0.0 and p.vitals is None

def test_effects_are_distinct_types():
    assert isinstance(Speak("hi"), Speak)
    assert ShowScreen("idle", {}).view == "idle"
    assert EngineCmd("start").cmd == "start"
    assert PublishResults({"x": 1}).payload == {"x": 1}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/test_types.py -v`
Expected: FAIL — `ModuleNotFoundError`/`ImportError`.

- [ ] **Step 3: Write minimal implementation**

```python
# core/types.py
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/test_types.py -v`
Expected: PASS (3 tests).

- [ ] **Step 5: Commit**

```bash
git add shenai_health_scan/shenai_health_scan/core/types.py shenai_health_scan/tests/test_types.py
git commit -m "feat: core types for scan state machine"
```

### Task 2: ScanOrchestrator state machine

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/core/orchestrator.py`
- Test: `shenai_health_scan/tests/test_orchestrator.py`

The orchestrator is pure: `request_scan()` sets a thread-safe flag; `on_tick(poll, now)` returns a list of `Effect`s and advances state. Timeouts use the injected `now` (monotonic seconds).

- [ ] **Step 1: Write the failing tests**

```python
# tests/test_orchestrator.py
from shenai_health_scan.core.orchestrator import ScanOrchestrator
from shenai_health_scan.core.types import (
    ScanState, FaceHint, EnginePoll, Vitals, EngineCmd, Speak, ShowScreen, PublishResults,
)

def mk(**kw):
    base = dict(face_present=True)
    base.update(kw)
    return EnginePoll(**base)

def test_starts_idle():
    o = ScanOrchestrator()
    assert o.state == ScanState.IDLE

def test_idle_emits_nothing_until_triggered():
    o = ScanOrchestrator()
    assert o.on_tick(mk(face_present=False), now=0.0) == []
    assert o.state == ScanState.IDLE

def test_trigger_moves_to_acquire_and_resets_engine():
    o = ScanOrchestrator()
    o.request_scan()
    effects = o.on_tick(mk(face_present=False), now=1.0)
    assert o.state == ScanState.ACQUIRE_FACE
    assert any(isinstance(e, EngineCmd) and e.cmd == "reset" for e in effects)
    assert any(isinstance(e, Speak) for e in effects)

def test_acquire_starts_measurement_when_ready():
    o = ScanOrchestrator()
    o.request_scan(); o.on_tick(mk(face_present=False), now=0.0)
    effects = o.on_tick(mk(is_ready=True, face_hint=FaceHint.READY), now=1.0)
    assert o.state == ScanState.MEASURING
    assert any(isinstance(e, EngineCmd) and e.cmd == "start" for e in effects)

def test_acquire_face_timeout_fails():
    o = ScanOrchestrator(acquire_face_timeout=5.0)
    o.request_scan(); o.on_tick(mk(face_present=False), now=0.0)
    effects = o.on_tick(mk(face_present=False), now=6.0)
    assert o.state == ScanState.FAILED
    assert any(isinstance(e, Speak) for e in effects)

def test_measuring_finishes_and_publishes():
    o = ScanOrchestrator()
    o.request_scan(); o.on_tick(mk(), now=0.0)
    o.on_tick(mk(is_ready=True), now=1.0)  # -> MEASURING
    v = Vitals(heart_rate_bpm=72, systolic_bp_mmhg=120, diastolic_bp_mmhg=80)
    effects = o.on_tick(mk(finished=True, vitals=v), now=2.0)
    assert o.state == ScanState.DONE
    assert any(isinstance(e, ShowScreen) and e.view == "result_card" for e in effects)
    assert any(isinstance(e, PublishResults) for e in effects)

def test_measuring_bad_signal_fails():
    o = ScanOrchestrator(max_measure_seconds=60, min_signal_quality=0.3)
    o.request_scan(); o.on_tick(mk(), now=0.0); o.on_tick(mk(is_ready=True), now=1.0)
    effects = o.on_tick(mk(failed=True), now=3.0)
    assert o.state == ScanState.FAILED
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: FAIL — import error.

- [ ] **Step 3: Implement**

```python
# core/orchestrator.py
from __future__ import annotations
import threading
from typing import List, Optional
from .types import (
    ScanState, FaceHint, EnginePoll, Vitals, ResultPayload,
    Speak, ShowScreen, EngineCmd, PublishResults,
)

Effect = object  # union of Speak/ShowScreen/EngineCmd/PublishResults

_HINT_SPEECH = {
    FaceHint.NO_FACE: "Please stand in front of me and look at my eyes.",
    FaceHint.TOO_FAR: "Come a little closer, please.",
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
                self._enter(ScanState.DONE, now)
                return [ShowScreen("result_card", {"vitals": poll.vitals.to_dict()}),
                        Speak(self._summary_speech(poll.vitals)),
                        PublishResults({"vitals": poll.vitals.to_dict(),
                                        "quality": {"average_signal_quality": poll.signal_quality,
                                                    "bad_signal_seconds": poll.bad_signal_seconds}})]
            if poll.failed or (now - self._state_entered_at > self._max_measure):
                self._enter(ScanState.FAILED, now)
                return [EngineCmd("stop"), ShowScreen("error", {}),
                        Speak("I couldn't complete the reading. Let's try again later.")]
            return [ShowScreen("measuring", {"progress": poll.progress})]

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
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/test_orchestrator.py -v`
Expected: PASS (7 tests).

- [ ] **Step 5: Commit**

```bash
git add shenai_health_scan/shenai_health_scan/core/orchestrator.py shenai_health_scan/tests/test_orchestrator.py
git commit -m "feat: ScanOrchestrator pure state machine"
```

---

## Phase 2 — Config (full TDD)

### Task 3: ScanConfig

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/core/config.py`
- Test: `shenai_health_scan/tests/test_config.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_config.py
from shenai_health_scan.core.config import ScanConfig

def test_defaults():
    c = ScanConfig.from_dict({})
    assert c.camera_topic == "/aima/hal/sensor/rgbd_head_front/rgb_image"
    assert c.submit_fps == 30
    assert c.offline is False
    assert "service" in c.enabled_triggers

def test_overrides_and_unknown_keys_ignored():
    c = ScanConfig.from_dict({"submit_fps": 25, "api_key": "K", "junk": 1,
                              "publisher": {"endpoint": "http://x/y"}})
    assert c.submit_fps == 25 and c.api_key == "K"
    assert c.publisher.endpoint == "http://x/y"
```

- [ ] **Step 2: Run — expect FAIL.** `python -m pytest tests/test_config.py -v`

- [ ] **Step 3: Implement**

```python
# core/config.py
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
    measurement_preset: str = "ONE_MINUTE_HR_HRV_BR_BP"
    precision_mode: str = "RELAXED"
    camera_topic: str = "/aima/hal/sensor/rgbd_head_front/rgb_image"
    submit_fps: int = 30
    enabled_triggers: List[str] = field(default_factory=lambda: ["service"])
    acquire_face_timeout: float = 20.0
    max_measure_seconds: float = 75.0
    min_signal_quality: float = 0.0
    publisher: PublisherConfig = field(default_factory=PublisherConfig)

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "ScanConfig":
        d = d or {}
        return cls(
            api_key=d.get("api_key", ""),
            offline=bool(d.get("offline", False)),
            measurement_preset=d.get("measurement_preset", "ONE_MINUTE_HR_HRV_BR_BP"),
            precision_mode=d.get("precision_mode", "RELAXED"),
            camera_topic=d.get("camera_topic", "/aima/hal/sensor/rgbd_head_front/rgb_image"),
            submit_fps=int(d.get("submit_fps", 30)),
            enabled_triggers=list(d.get("enabled_triggers", ["service"])),
            acquire_face_timeout=float(d.get("acquire_face_timeout", 20.0)),
            max_measure_seconds=float(d.get("max_measure_seconds", 75.0)),
            min_signal_quality=float(d.get("min_signal_quality", 0.0)),
            publisher=PublisherConfig.from_dict(d.get("publisher", {})),
        )
```

> Note: confirm the exact `MeasurementPreset` enum name against `shenai_sdk/enums.py` on the workstation; adjust the default string if needed. `ShenAiEngine` maps the string to the enum (Task 6).

- [ ] **Step 4: Run — expect PASS.** `python -m pytest tests/test_config.py -v`

- [ ] **Step 5: Commit** `git commit -am "feat: ScanConfig loader"`

---

## Phase 3 — Engine interface + MockEngine (full TDD)

### Task 4: Engine base + MockEngine

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/engine/base.py`
- Create: `shenai_health_scan/shenai_health_scan/engine/mock_engine.py`
- Test: `shenai_health_scan/tests/test_mock_engine.py`

MockEngine simulates a scan deterministically by frame count so the whole pipeline runs without the SDK: face appears after `face_after` frames, becomes ready after `ready_after`, progresses, finishes at `finish_after` with fixed vitals.

- [ ] **Step 1: Failing test**

```python
# tests/test_mock_engine.py
from shenai_health_scan.engine.mock_engine import MockEngine
from shenai_health_scan.core.types import FaceHint

def feed(engine, n):
    for _ in range(n):
        engine.submit(b"\x00", 1, 1, 3, -1)
    return engine.poll()

def test_progression():
    e = MockEngine(face_after=2, ready_after=4, finish_after=8)
    e.begin_session(); 
    p = feed(e, 1); assert p.face_present is False
    p = feed(e, 3); assert p.face_present is True and p.is_ready is False
    e.start()
    p = feed(e, 4); assert p.is_ready is True
    p = feed(e, 5); assert p.finished is True and p.vitals.heart_rate_bpm == 72
    r = e.final_results()
    assert r.heart_rate_bpm == 72
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
# engine/base.py
from __future__ import annotations
from typing import Optional, Protocol
from ..core.types import EnginePoll, Vitals

class EngineBase(Protocol):
    def begin_session(self) -> None: ...
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def submit(self, data, width: int, height: int, stride: int, ts_ns: int) -> None: ...
    def poll(self) -> EnginePoll: ...
    def final_results(self) -> Optional[Vitals]: ...
    def close(self) -> None: ...
```

```python
# engine/mock_engine.py
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
        face = self._n >= self._face_after
        ready = self._n >= self._ready_after
        finished = self._started and self._n >= self._finish_after
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
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit** `git commit -am "feat: engine interface + MockEngine"`

---

## Phase 4 — ResultsPublisher (full TDD with mock HTTP server)

### Task 5: ResultsPublisher

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/publisher/results_publisher.py`
- Test: `shenai_health_scan/tests/test_results_publisher.py`

Threaded queue; worker POSTs JSON via `requests`; on failure retries with backoff, then writes a dead-letter file. `flush(timeout)` for deterministic tests.

- [ ] **Step 1: Failing test** (uses `http.server` in a thread)

```python
# tests/test_results_publisher.py
import json, threading, http.server, tempfile, os
from shenai_health_scan.publisher.results_publisher import ResultsPublisher

class _Handler(http.server.BaseHTTPRequestHandler):
    received = []
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        _Handler.received.append(json.loads(self.rfile.read(n)))
        self.send_response(200); self.end_headers()
    def log_message(self, *a): pass

def _server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def test_posts_payload():
    _Handler.received.clear()
    srv = _server(); port = srv.server_address[1]
    pub = ResultsPublisher(endpoint=f"http://127.0.0.1:{port}/r", auth_header=None)
    pub.start(); pub.publish({"hello": "world"}); pub.flush(timeout=3.0); pub.stop()
    srv.shutdown()
    assert _Handler.received == [{"hello": "world"}]

def test_dead_letter_on_failure():
    d = tempfile.mkdtemp()
    pub = ResultsPublisher(endpoint="http://127.0.0.1:1/none", auth_header=None,
                           max_retries=1, timeout_sec=0.2, dead_letter_path=d)
    pub.start(); pub.publish({"x": 1}); pub.flush(timeout=5.0); pub.stop()
    files = os.listdir(d)
    assert len(files) == 1 and json.load(open(os.path.join(d, files[0])))["x"] == 1
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
# publisher/results_publisher.py
from __future__ import annotations
import json, os, queue, threading, time, uuid
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:  # allow import without requests; fail only on actual POST
    requests = None


class ResultsPublisher:
    def __init__(self, endpoint: Optional[str], auth_header: Optional[str] = None,
                 timeout_sec: float = 5.0, max_retries: int = 3,
                 dead_letter_path: str = "dead_letter"):
        self._endpoint = endpoint
        self._auth = auth_header
        self._timeout = timeout_sec
        self._max_retries = max_retries
        self._dlp = dead_letter_path
        self._q: "queue.Queue" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def publish(self, payload: Dict[str, Any]):
        self._q.put(payload)

    def flush(self, timeout: float = 5.0):
        end = time.time() + timeout
        while not self._q.empty() and time.time() < end:
            time.sleep(0.02)

    def stop(self):
        self._stop.set()
        self._q.put(None)
        if self._thread:
            self._thread.join(timeout=3.0)

    def _run(self):
        while not self._stop.is_set():
            item = self._q.get()
            if item is None:
                break
            self._deliver(item)

    def _deliver(self, payload: Dict[str, Any]):
        if not self._endpoint or requests is None:
            return self._dead_letter(payload)
        headers = {"Content-Type": "application/json"}
        if self._auth:
            headers["Authorization"] = self._auth
        delay = 0.5
        for attempt in range(self._max_retries):
            try:
                resp = requests.post(self._endpoint, json=payload, headers=headers,
                                     timeout=self._timeout)
                if 200 <= resp.status_code < 300:
                    return
            except Exception:
                pass
            time.sleep(delay); delay *= 2
        self._dead_letter(payload)

    def _dead_letter(self, payload: Dict[str, Any]):
        os.makedirs(self._dlp, exist_ok=True)
        fn = os.path.join(self._dlp, f"result_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}.json")
        with open(fn, "w") as f:
            json.dump(payload, f)
```

- [ ] **Step 4: Run — expect PASS.** (Ensure `requests` installed: `pip install requests`.)

- [ ] **Step 5: Commit** `git commit -am "feat: threaded ResultsPublisher with dead-letter"`

---

## Phase 5 — RobotIO: base, ConsoleIO, cards (TDD where pure)

### Task 6: RobotIO base + ConsoleIO + result card renderer

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/robot_io/base.py`
- Create: `shenai_health_scan/shenai_health_scan/robot_io/console_io.py`
- Create: `shenai_health_scan/shenai_health_scan/robot_io/cards.py`
- Test: `shenai_health_scan/tests/test_cards.py`

- [ ] **Step 1: Failing test**

```python
# tests/test_cards.py
import numpy as np
from shenai_health_scan.robot_io.cards import render_result_card

def test_render_returns_png_bytes():
    png = render_result_card({"heart_rate_bpm": 72, "systolic_bp_mmhg": 120,
                              "diastolic_bp_mmhg": 80})
    assert isinstance(png, (bytes, bytearray)) and png[:8] == b"\x89PNG\r\n\x1a\n"
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
# robot_io/base.py
from __future__ import annotations
from typing import Protocol, Dict, Any

class RobotIO(Protocol):
    def speak(self, text: str, priority: int = 6) -> None: ...
    def show(self, view: str, data: Dict[str, Any]) -> None: ...
```

```python
# robot_io/cards.py
from __future__ import annotations
from typing import Dict, Any
import cv2
import numpy as np

_LABELS = [("heart_rate_bpm", "Heart Rate", "bpm"),
           ("hrv_sdnn_ms", "HRV", "ms"),
           ("breathing_rate_bpm", "Breathing", "/min"),
           ("stress_index", "Stress", ""),
           ("systolic_bp_mmhg", "BP (sys)", "mmHg"),
           ("diastolic_bp_mmhg", "BP (dia)", "mmHg")]

def render_result_card(vitals: Dict[str, Any], width=1280, height=720) -> bytes:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (30, 30, 30)
    cv2.putText(img, "Health Scan Results", (60, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 3, cv2.LINE_AA)
    y = 200
    for key, label, unit in _LABELS:
        if key in vitals and vitals[key] is not None:
            val = vitals[key]
            txt = f"{label}: {val:.0f} {unit}".strip()
            cv2.putText(img, txt, (60, y), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                        (0, 220, 120), 2, cv2.LINE_AA)
            y += 80
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""
```

```python
# robot_io/console_io.py
from __future__ import annotations
from typing import Dict, Any

class ConsoleIO:
    def speak(self, text: str, priority: int = 6) -> None:
        print(f"[TTS] {text}")
    def show(self, view: str, data: Dict[str, Any]) -> None:
        print(f"[SCREEN:{view}] {data}")
```

- [ ] **Step 4: Run — expect PASS.**

- [ ] **Step 5: Commit** `git commit -am "feat: RobotIO base, ConsoleIO, result card renderer"`

---

## Phase 6 — Camera base + FakeCamera, triggers base + ManualTrigger

### Task 7: Camera base + FakeCamera

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/camera/base.py`
- Create: `shenai_health_scan/shenai_health_scan/camera/fake_camera.py`

(No new unit test file required — exercised by the demo integration test in Task 10. FakeCamera reads a video file or webcam via cv2 and returns BGR bytes.)

- [ ] **Step 1: Implement**

```python
# camera/base.py
from __future__ import annotations
from typing import Protocol, Optional, Tuple

Frame = Tuple[bytes, int, int, int, int]  # data, width, height, stride, capture_ts_ns

class CameraSource(Protocol):
    def start(self) -> None: ...
    def stop(self) -> None: ...
    def get_latest(self) -> Optional[Frame]: ...
    @property
    def measured_fps(self) -> float: ...
```

```python
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
```

- [ ] **Step 2: Commit** `git commit -am "feat: CameraSource base + FakeCamera"`

### Task 8: Trigger base + ManualTrigger

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/triggers/base.py`
- Create: `shenai_health_scan/shenai_health_scan/triggers/manual_trigger.py`

- [ ] **Step 1: Implement**

```python
# triggers/base.py
from __future__ import annotations
from typing import Protocol, Callable

class ScanTrigger(Protocol):
    def start(self, on_trigger: Callable[[], None]) -> None: ...
    def stop(self) -> None: ...
```

```python
# triggers/manual_trigger.py
from __future__ import annotations
from typing import Callable, Optional

class ManualTrigger:
    """Programmatic trigger for demo/tests; call fire() to start a scan."""
    def __init__(self):
        self._cb: Optional[Callable[[], None]] = None
    def start(self, on_trigger: Callable[[], None]) -> None:
        self._cb = on_trigger
    def fire(self) -> None:
        if self._cb: self._cb()
    def stop(self) -> None:
        self._cb = None
```

- [ ] **Step 2: Commit** `git commit -am "feat: ScanTrigger base + ManualTrigger"`

---

## Phase 7 — MeasurementLoop + ScanApp runner (TDD via fakes)

### Task 9: MeasurementLoop

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/loop.py`
- Test: `shenai_health_scan/tests/test_loop.py`

The loop owns a thread that, at `submit_fps` cadence: pulls latest frame, submits to engine, polls, calls `orchestrator.on_tick`, and dispatches effects to engine/io/publisher. It exposes `tick_once()` for deterministic testing (no real timing).

- [ ] **Step 1: Failing test**

```python
# tests/test_loop.py
from shenai_health_scan.loop import MeasurementLoop
from shenai_health_scan.core.orchestrator import ScanOrchestrator
from shenai_health_scan.engine.mock_engine import MockEngine
from shenai_health_scan.core.types import ScanState

class RecIO:
    def __init__(self): self.spoken=[]; self.shown=[]
    def speak(self, t, priority=6): self.spoken.append(t)
    def show(self, v, d): self.shown.append(v)

class RecPub:
    def __init__(self): self.payloads=[]
    def publish(self, p): self.payloads.append(p)

class OneFrameCam:
    def start(self): pass
    def stop(self): pass
    def get_latest(self): return (b"\x00", 1, 1, 3, 1)
    @property
    def measured_fps(self): return 30.0

def test_loop_runs_full_scan_to_done():
    eng = MockEngine(face_after=1, ready_after=2, finish_after=4)
    orch = ScanOrchestrator()
    io, pub = RecIO(), RecPub()
    loop = MeasurementLoop(OneFrameCam(), eng, orch, io, pub, submit_fps=30)
    orch.request_scan()
    for i in range(10):
        loop.tick_once(now=float(i))
    assert orch.state == ScanState.DONE
    assert any("done" in s.lower() for s in io.spoken)
    assert len(pub.payloads) == 1
    assert "measurement_id" in pub.payloads[0]
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
# loop.py
from __future__ import annotations
import threading, time, datetime
from typing import Optional
from .core.types import EngineCmd, Speak, ShowScreen, PublishResults

class MeasurementLoop:
    def __init__(self, camera, engine, orchestrator, robot_io, publisher,
                 submit_fps: int = 30, logger=None):
        self.camera = camera
        self.engine = engine
        self.orch = orchestrator
        self.io = robot_io
        self.pub = publisher
        self.period = 1.0 / submit_fps
        self.log = logger
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        self.camera.start()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            self.tick_once(now=time.monotonic())
            time.sleep(self.period)

    def tick_once(self, now: float):
        frame = self.camera.get_latest()
        if frame is not None:
            data, w, h, stride, ts = frame
            try:
                self.engine.submit(data, w, h, stride, ts)
            except Exception as e:
                if self.log: self.log(f"submit_frame failed: {e}")
        poll = self.engine.poll()
        for eff in self.orch.on_tick(poll, now):
            self._dispatch(eff)

    def _dispatch(self, eff):
        if isinstance(eff, EngineCmd):
            if eff.cmd == "reset": self.engine.begin_session()
            elif eff.cmd == "start": self.engine.start()
            elif eff.cmd == "stop": self.engine.stop()
        elif isinstance(eff, Speak):
            if eff.text: self.io.speak(eff.text)
        elif isinstance(eff, ShowScreen):
            self.io.show(eff.view, eff.data)
        elif isinstance(eff, PublishResults):
            self.pub.publish(self._enrich(eff.payload))

    def _enrich(self, payload: dict) -> dict:
        mid = tid = ""
        try:
            mid = self.engine.measurement_id()
            tid = self.engine.trace_id()
        except Exception:
            pass
        payload = dict(payload)
        payload["measurement_id"] = mid
        payload["trace_id"] = tid
        payload["timestamp"] = datetime.datetime.utcnow().isoformat() + "Z"
        return payload

    def stop(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=2.0)
        self.camera.stop()
```

> `MockEngine` needs `measurement_id()`/`trace_id()` for `_enrich`. Add to MockEngine:
> ```python
>     def measurement_id(self): return "mock-measurement"
>     def trace_id(self): return "mock-trace"
> ```
> (Add these two methods and re-run Task 4 tests — still pass.)

- [ ] **Step 4: Run — expect PASS.** `python -m pytest tests/test_loop.py -v`

- [ ] **Step 5: Commit** `git commit -am "feat: MeasurementLoop with deterministic tick_once"`

### Task 10: ScanApp runner + demo entrypoint (integration test, off-robot)

**Files:**
- Create: `shenai_health_scan/shenai_health_scan/runner.py`
- Create: `shenai_health_scan/shenai_health_scan/demo.py`
- Test: `shenai_health_scan/tests/test_runner_demo.py`

`ScanApp` wires components, builds the orchestrator from config, starts publisher + loop + triggers, and exposes `request_scan()`. `demo.py` builds a ScanApp with FakeCamera + MockEngine (or real x64 engine via `--real`) + ConsoleIO + ManualTrigger and runs one scan.

- [ ] **Step 1: Failing test**

```python
# tests/test_runner_demo.py
import time
from shenai_health_scan.runner import ScanApp
from shenai_health_scan.core.config import ScanConfig
from shenai_health_scan.engine.mock_engine import MockEngine
from shenai_health_scan.robot_io.console_io import ConsoleIO
from shenai_health_scan.triggers.manual_trigger import ManualTrigger
from shenai_health_scan.core.types import ScanState

class FastCam:
    def start(self): pass
    def stop(self): pass
    def get_latest(self): return (b"\x00", 1, 1, 3, 1)
    @property
    def measured_fps(self): return 30.0

def test_scanapp_end_to_end_mock():
    cfg = ScanConfig.from_dict({"submit_fps": 1000})
    trig = ManualTrigger()
    app = ScanApp(cfg, camera=FastCam(),
                  engine=MockEngine(face_after=1, ready_after=2, finish_after=4),
                  robot_io=ConsoleIO(), triggers=[trig])
    app.start(); trig.fire()
    for _ in range(50):
        if app.orch.state in (ScanState.DONE, ScanState.FAILED): break
        time.sleep(0.01)
    app.stop()
    assert app.orch.state == ScanState.DONE
```

- [ ] **Step 2: Run — expect FAIL.**

- [ ] **Step 3: Implement**

```python
# runner.py
from __future__ import annotations
from typing import List, Optional
from .core.config import ScanConfig
from .core.orchestrator import ScanOrchestrator
from .publisher.results_publisher import ResultsPublisher
from .loop import MeasurementLoop

class ScanApp:
    def __init__(self, config: ScanConfig, camera, engine, robot_io,
                 triggers: List, logger=None):
        self.config = config
        self.orch = ScanOrchestrator(
            acquire_face_timeout=config.acquire_face_timeout,
            max_measure_seconds=config.max_measure_seconds,
            min_signal_quality=config.min_signal_quality)
        self.publisher = ResultsPublisher(
            endpoint=config.publisher.endpoint,
            auth_header=config.publisher.auth_header,
            timeout_sec=config.publisher.timeout_sec,
            max_retries=config.publisher.max_retries,
            dead_letter_path=config.publisher.dead_letter_path)
        self.loop = MeasurementLoop(camera, engine, self.orch, robot_io,
                                    self.publisher, submit_fps=config.submit_fps,
                                    logger=logger)
        self.triggers = triggers

    def request_scan(self):
        self.orch.request_scan()

    def start(self):
        self.publisher.start()
        self.loop.start()
        for t in self.triggers:
            t.start(self.request_scan)

    def stop(self):
        for t in self.triggers:
            t.stop()
        self.loop.stop()
        self.publisher.flush(timeout=3.0)
        self.publisher.stop()
```

```python
# demo.py
from __future__ import annotations
import argparse, time
from .core.config import ScanConfig
from .engine.mock_engine import MockEngine
from .camera.fake_camera import FakeCamera
from .robot_io.console_io import ConsoleIO
from .triggers.manual_trigger import ManualTrigger
from .runner import ScanApp
from .core.types import ScanState

def main():
    ap = argparse.ArgumentParser(description="Off-robot Shen.AI scan demo")
    ap.add_argument("--source", default="0", help="webcam index or video file path")
    ap.add_argument("--real", action="store_true", help="use real Shen.AI x64 SDK engine")
    ap.add_argument("--api-key", default="")
    args = ap.parse_args()

    source = int(args.source) if args.source.isdigit() else args.source
    cfg = ScanConfig.from_dict({"submit_fps": 30, "api_key": args.api_key})

    if args.real:
        from .engine.shenai_engine import ShenAiEngine
        engine = ShenAiEngine(cfg)
    else:
        engine = MockEngine()

    cam = FakeCamera(source=source, fps=30.0)
    trig = ManualTrigger()
    app = ScanApp(cfg, camera=cam, engine=engine, robot_io=ConsoleIO(), triggers=[trig])
    app.start()
    print(">> press Enter to start a scan, Ctrl-C to quit")
    try:
        while True:
            input()
            trig.fire()
            while app.orch.state not in (ScanState.DONE, ScanState.FAILED):
                time.sleep(0.1)
            print(f">> scan finished: {app.orch.state.value}")
    except KeyboardInterrupt:
        pass
    finally:
        app.stop()

if __name__ == "__main__":
    main()
```

- [ ] **Step 4: Run — expect PASS.** `python -m pytest tests/test_runner_demo.py -v`
- [ ] **Step 5: Manual demo (webcam, mock engine):** `python -m shenai_health_scan.demo --source 0` → press Enter → console shows TTS/screen lines progressing to DONE.
- [ ] **Step 6: Commit** `git commit -am "feat: ScanApp runner + off-robot demo entrypoint"`

---

## Phase 8 — Real adapters (write + on-robot/HW verification; not unit-tested off-robot)

> These import ROS 2 / the SDK lazily. They cannot be unit-tested on the workstation without `rclpy`/`aimdk_msgs`/the `.so`. Verify with the SDK and on the robot.

### Task 11: ShenAiEngine (real SDK wrapper)

**Files:** Create `shenai_health_scan/shenai_health_scan/engine/shenai_engine.py`

- [ ] **Step 1: Implement**

```python
# engine/shenai_engine.py
from __future__ import annotations
from typing import Optional
from ..core.types import EnginePoll, Vitals, FaceHint
from ..core.config import ScanConfig

class ShenAiEngine:
    """Wraps the Shen.AI headless Python SDK. The only owner of the SDK context."""
    def __init__(self, config: ScanConfig):
        from shenai_sdk import ShenaiSDK, MeasurementPreset, PrecisionMode, MeasurementState, FaceState
        self._MeasurementState = MeasurementState
        self._FaceState = FaceState
        self._sdk = ShenaiSDK(api_key=config.api_key, offline=config.offline)
        self._sdk.precision_mode = getattr(PrecisionMode, config.precision_mode)
        self._sdk.measurement_preset = getattr(MeasurementPreset, config.measurement_preset)

    def begin_session(self): self._sdk.reset_measurement_session()
    def start(self): self._sdk.start_measurement()
    def stop(self): self._sdk.stop_measurement()

    def submit(self, data, width, height, stride, ts_ns):
        self._sdk.submit_frame(data, width=width, height=height,
                               stride_bytes=stride, timestamp_ns=ts_ns)

    def poll(self) -> EnginePoll:
        face_state = self._sdk.get_face_state()
        face_present = face_state not in (self._FaceState.NO_FACE,) if hasattr(self._FaceState, "NO_FACE") else True
        is_ready = self._sdk.is_ready_to_start_measurement()
        progress = self._sdk.get_progress_percent() / 100.0
        mstate = self._sdk.get_measurement_state()
        finished = mstate == self._MeasurementState.FINISHED
        failed = mstate == getattr(self._MeasurementState, "FAILED", object())
        sq = self._sdk.get_current_signal_quality_metric()
        bad = self._sdk.get_total_bad_signal_seconds()
        vitals = self._final_vitals() if finished else None
        return EnginePoll(face_present=face_present, is_ready=is_ready, progress=progress,
                          finished=finished, failed=failed, signal_quality=sq,
                          bad_signal_seconds=bad, face_hint=self._hint(face_state, is_ready),
                          vitals=vitals)

    def _hint(self, face_state, is_ready) -> FaceHint:
        if hasattr(self._FaceState, "NO_FACE") and face_state == self._FaceState.NO_FACE:
            return FaceHint.NO_FACE
        if is_ready:
            return FaceHint.READY
        return FaceHint.HOLD_STILL

    def _final_vitals(self) -> Optional[Vitals]:
        r = self._sdk.get_measurement_results()
        if r is None: return None
        return Vitals(heart_rate_bpm=r.heart_rate_bpm, hrv_sdnn_ms=r.hrv_sdnn_ms,
                      breathing_rate_bpm=r.breathing_rate_bpm, stress_index=r.stress_index,
                      systolic_bp_mmhg=r.systolic_bp_mmhg, diastolic_bp_mmhg=r.diastolic_bp_mmhg)

    def final_results(self) -> Optional[Vitals]: return self._final_vitals()
    def measurement_id(self) -> str: return self._sdk.get_measurement_id()
    def trace_id(self) -> str: return self._sdk.get_trace_id()
    def close(self):
        self._sdk.close(); self._sdk.destroy_runtime()
```

- [ ] **Step 2: Verify against SDK** on workstation (x64 build) with a webcam:
  `python -m shenai_health_scan.demo --real --api-key <KEY> --source 0`
  Confirm `FaceState`/`MeasurementState`/`PrecisionMode`/`MeasurementPreset` enum member names match `shenai_sdk/enums.py`; fix `getattr` names if the SDK uses different identifiers.
- [ ] **Step 3: Commit** `git commit -am "feat: ShenAiEngine SDK wrapper"`

### Task 12: RosCamera

**Files:** Create `shenai_health_scan/shenai_health_scan/camera/ros_camera.py`

- [ ] **Step 1: Implement**

```python
# camera/ros_camera.py
from __future__ import annotations
import threading, time
from typing import Optional, Tuple

class RosCamera:
    """ROS 2 subscriber -> latest BGR frame. Construct with a live rclpy Node."""
    def __init__(self, node, topic: str):
        from sensor_msgs.msg import Image
        from cv_bridge import CvBridge
        from rclpy.qos import QoSProfile, QoSReliabilityPolicy, QoSHistoryPolicy
        import cv2
        self._cv2 = cv2
        self._bridge = CvBridge()
        self._lock = threading.Lock()
        self._latest: Optional[Tuple[bytes, int, int, int, int]] = None
        self._count = 0
        self._t0 = time.time()
        qos = QoSProfile(reliability=QoSReliabilityPolicy.BEST_EFFORT,
                         history=QoSHistoryPolicy.KEEP_LAST, depth=5)
        self._sub = node.create_subscription(Image, topic, self._cb, qos)
        node.get_logger().info(f"RosCamera subscribed to {topic}")

    def _cb(self, msg):
        img = self._bridge.imgmsg_to_cv2(msg, desired_encoding="passthrough")
        enc = msg.encoding.lower()
        if enc == "rgb8":
            img = self._cv2.cvtColor(img, self._cv2.COLOR_RGB2BGR)
        elif enc == "mono8":
            img = self._cv2.cvtColor(img, self._cv2.COLOR_GRAY2BGR)
        h, w = img.shape[:2]
        with self._lock:
            self._latest = (img.tobytes(), w, h, w * 3, time.monotonic_ns())
            self._count += 1

    def start(self): pass
    def stop(self): pass
    def get_latest(self):
        with self._lock:
            return self._latest

    @property
    def measured_fps(self) -> float:
        dt = time.time() - self._t0
        return self._count / dt if dt > 0 else 0.0
```

- [ ] **Step 2: On-robot verification** (after Task 15 wiring): confirm `measured_fps >= submit_fps`; if low, switch `camera_topic` to a higher-rate source or raise the issue with AgiBot.
- [ ] **Step 3: Commit** `git commit -am "feat: RosCamera subscriber adapter"`

### Task 13: RosIO (PlayTts + PlayVideo)

**Files:** Create `shenai_health_scan/shenai_health_scan/robot_io/ros_io.py`

- [ ] **Step 1: Implement**

```python
# robot_io/ros_io.py
from __future__ import annotations
import os, time, tempfile
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
                path = os.path.join(self._card_dir, f"card_{int(time.time()*1000)}.png")
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
```

> **Open item:** confirm on-device whether `PlayVideo` accepts a still image path or strictly video; if video-only, render a short looped MP4 with `cv2.VideoWriter` instead of a PNG. `cards.py` is the single place to change.

- [ ] **Step 2: On-robot verification:** call `speak`/`show` and observe face screen + audio.
- [ ] **Step 3: Commit** `git commit -am "feat: RosIO (PlayTts + PlayVideo)"`

### Task 14: ROS triggers (Service, Touch, Topic)

**Files:** Create `service_trigger.py`, `touch_trigger.py`, `topic_trigger.py` under `triggers/`.

- [ ] **Step 1: Implement**

```python
# triggers/service_trigger.py
from __future__ import annotations
from typing import Callable

class ServiceTrigger:
    """ROS 2 service ~/start_scan (std_srvs/Trigger). Always-on baseline trigger."""
    def __init__(self, node, service_name: str = "~/start_scan"):
        self._node = node
        self._name = service_name
        self._srv = None
    def start(self, on_trigger: Callable[[], None]) -> None:
        from std_srvs.srv import Trigger
        def _cb(request, response):
            on_trigger()
            response.success = True
            response.message = "scan requested"
            return response
        self._srv = self._node.create_service(Trigger, self._name, _cb)
        self._node.get_logger().info(f"ServiceTrigger ready on {self._name}")
    def stop(self) -> None:
        if self._srv is not None:
            self._node.destroy_service(self._srv); self._srv = None
```

```python
# triggers/touch_trigger.py
from __future__ import annotations
from typing import Callable

class TouchTrigger:
    """Starts a scan on a head pat. Subscribes /aima/hal/sensor/touch_head."""
    def __init__(self, node, topic: str = "/aima/hal/sensor/touch_head",
                 event: str = "PAT_TWICE"):
        self._node = node
        self._topic = topic
        self._event_name = event
        self._sub = None
    def start(self, on_trigger: Callable[[], None]) -> None:
        from aimdk_msgs.msg import TouchState
        want = getattr(TouchState, self._event_name)
        def _cb(msg):
            if msg.event_type == want:
                on_trigger()
        self._sub = self._node.create_subscription(TouchState, self._topic, _cb, 10)
        self._node.get_logger().info(
            f"TouchTrigger ready on {self._topic} ({self._event_name})")
    def stop(self) -> None:
        if self._sub is not None:
            self._node.destroy_subscription(self._sub); self._sub = None
```

```python
# triggers/topic_trigger.py
from __future__ import annotations
from typing import Callable

class TopicTrigger:
    """Generic trigger: any message on a std_msgs/Empty topic starts a scan."""
    def __init__(self, node, topic: str = "~/start_scan_topic"):
        self._node = node
        self._topic = topic
        self._sub = None
    def start(self, on_trigger: Callable[[], None]) -> None:
        from std_msgs.msg import Empty
        self._sub = self._node.create_subscription(Empty, self._topic,
                                                   lambda _m: on_trigger(), 10)
        self._node.get_logger().info(f"TopicTrigger ready on {self._topic}")
    def stop(self) -> None:
        if self._sub is not None:
            self._node.destroy_subscription(self._sub); self._sub = None
```

- [ ] **Step 2: Commit** `git commit -am "feat: ROS triggers (service/touch/topic)"`

### Task 15: ROS 2 node entrypoint

**Files:** Create `shenai_health_scan/shenai_health_scan/node.py`

- [ ] **Step 1: Implement**

```python
# node.py
from __future__ import annotations
import rclpy
from rclpy.node import Node
from .core.config import ScanConfig
from .runner import ScanApp
from .engine.shenai_engine import ShenAiEngine
from .camera.ros_camera import RosCamera
from .robot_io.ros_io import RosIO
from .triggers.service_trigger import ServiceTrigger
from .triggers.touch_trigger import TouchTrigger
from .triggers.topic_trigger import TopicTrigger

_TRIGGER_FACTORIES = {
    "service": lambda node, cfg: ServiceTrigger(node),
    "touch": lambda node, cfg: TouchTrigger(node),
    "topic": lambda node, cfg: TopicTrigger(node),
}

class ShenAiHealthScanNode(Node):
    def __init__(self):
        super().__init__("shenai_health_scan")
        cfg = self._load_config()
        engine = ShenAiEngine(cfg)
        camera = RosCamera(self, cfg.camera_topic)
        robot_io = RosIO(self)
        triggers = [_TRIGGER_FACTORIES[t](self, cfg)
                    for t in cfg.enabled_triggers if t in _TRIGGER_FACTORIES]
        self.app = ScanApp(cfg, camera=camera, engine=engine, robot_io=robot_io,
                           triggers=triggers, logger=self.get_logger().warn)
        self.app.start()
        self.get_logger().info("Shen.AI health scan node started.")

    def _load_config(self) -> ScanConfig:
        self.declare_parameters("", [
            ("api_key", ""), ("offline", False),
            ("measurement_preset", "ONE_MINUTE_HR_HRV_BR_BP"),
            ("precision_mode", "RELAXED"),
            ("camera_topic", "/aima/hal/sensor/rgbd_head_front/rgb_image"),
            ("submit_fps", 30),
            ("enabled_triggers", ["service"]),
            ("acquire_face_timeout", 20.0), ("max_measure_seconds", 75.0),
            ("min_signal_quality", 0.0),
            ("publisher.endpoint", ""), ("publisher.auth_header", ""),
            ("publisher.timeout_sec", 5.0), ("publisher.max_retries", 3),
            ("publisher.dead_letter_path", "dead_letter"),
        ])
        g = lambda k: self.get_parameter(k).value
        return ScanConfig.from_dict({
            "api_key": g("api_key"), "offline": g("offline"),
            "measurement_preset": g("measurement_preset"),
            "precision_mode": g("precision_mode"),
            "camera_topic": g("camera_topic"), "submit_fps": g("submit_fps"),
            "enabled_triggers": list(g("enabled_triggers")),
            "acquire_face_timeout": g("acquire_face_timeout"),
            "max_measure_seconds": g("max_measure_seconds"),
            "min_signal_quality": g("min_signal_quality"),
            "publisher": {
                "endpoint": g("publisher.endpoint") or None,
                "auth_header": g("publisher.auth_header") or None,
                "timeout_sec": g("publisher.timeout_sec"),
                "max_retries": g("publisher.max_retries"),
                "dead_letter_path": g("publisher.dead_letter_path"),
            },
        })

def main(args=None):
    rclpy.init(args=args)
    node = ShenAiHealthScanNode()
    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.app.stop()
        node.destroy_node()
        if rclpy.ok():
            rclpy.shutdown()

if __name__ == "__main__":
    main()
```

- [ ] **Step 2: Commit** `git commit -am "feat: ROS 2 node entrypoint"`

---

## Phase 9 — ROS 2 packaging

### Task 16: package.xml, setup.py, params.yaml, launch

**Files:** Create `package.xml`, `setup.py`, `setup.cfg`, `resource/shenai_health_scan`, `config/params.yaml`, `launch/shenai_health_scan.launch.py`.

- [ ] **Step 1: `package.xml`**

```xml
<?xml version="1.0"?>
<package format="3">
  <name>shenai_health_scan</name>
  <version>0.1.0</version>
  <description>Shen.AI facial health scan on AgiBot X2</description>
  <maintainer email="liangkaifeng1987@gmail.com">Liang Kai Feng</maintainer>
  <license>Proprietary</license>
  <exec_depend>rclpy</exec_depend>
  <exec_depend>sensor_msgs</exec_depend>
  <exec_depend>std_msgs</exec_depend>
  <exec_depend>std_srvs</exec_depend>
  <exec_depend>cv_bridge</exec_depend>
  <exec_depend>aimdk_msgs</exec_depend>
  <test_depend>ament_copyright</test_depend>
  <test_depend>ament_flake8</test_depend>
  <export><build_type>ament_python</build_type></export>
</package>
```

- [ ] **Step 2: `setup.py`**

```python
from setuptools import find_packages, setup
import os
from glob import glob

package_name = "shenai_health_scan"

setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=["tests"]),
    data_files=[
        ("share/ament_index/resource_index/packages",
         ["resource/" + package_name]),
        ("share/" + package_name, ["package.xml"]),
        (os.path.join("share", package_name, "launch"), glob("launch/*.launch.py")),
        (os.path.join("share", package_name, "config"), glob("config/*.yaml")),
    ],
    install_requires=["setuptools", "requests"],
    zip_safe=True,
    maintainer="Liang Kai Feng",
    maintainer_email="liangkaifeng1987@gmail.com",
    description="Shen.AI facial health scan on AgiBot X2",
    license="Proprietary",
    entry_points={
        "console_scripts": [
            "scan_node = shenai_health_scan.node:main",
            "scan_demo = shenai_health_scan.demo:main",
        ],
    },
)
```

- [ ] **Step 3: `setup.cfg`**

```ini
[develop]
script_dir=$base/lib/shenai_health_scan
[install]
install_scripts=$base/lib/shenai_health_scan
```

- [ ] **Step 4: `resource/shenai_health_scan`** — empty marker file.

- [ ] **Step 5: `config/params.yaml`**

```yaml
shenai_health_scan:
  ros__parameters:
    api_key: ""                 # set via env-substitution or secret file at deploy
    offline: false
    measurement_preset: "ONE_MINUTE_HR_HRV_BR_BP"
    precision_mode: "RELAXED"
    camera_topic: "/aima/hal/sensor/rgbd_head_front/rgb_image"
    submit_fps: 30
    enabled_triggers: ["service", "touch"]
    acquire_face_timeout: 20.0
    max_measure_seconds: 75.0
    min_signal_quality: 0.0
    publisher.endpoint: ""      # third-party app URL
    publisher.auth_header: ""
    publisher.timeout_sec: 5.0
    publisher.max_retries: 3
    publisher.dead_letter_path: "/agibot/data/home/agi/shenai_dead_letter"
```

- [ ] **Step 6: `launch/shenai_health_scan.launch.py`**

```python
import os
from launch import LaunchDescription
from launch_ros.actions import Node
from ament_index_python.packages import get_package_share_directory

def generate_launch_description():
    params = os.path.join(
        get_package_share_directory("shenai_health_scan"), "config", "params.yaml")
    return LaunchDescription([
        Node(package="shenai_health_scan", executable="scan_node",
             name="shenai_health_scan", parameters=[params], output="screen"),
    ])
```

- [ ] **Step 7: Build & test on workstation (with ROS 2 Humble + aimdk_msgs in the workspace)**

```bash
cd ~/x2_ws
colcon build --packages-select shenai_health_scan
source install/setup.bash
python -m pytest src/shenai_health_scan/tests   # pure-core tests still pass
```

- [ ] **Step 8: Commit** `git commit -am "feat: ROS 2 packaging (package.xml/setup/launch/params)"`

---

## Phase 10 — Full test sweep + self-check

### Task 17: Green test suite

- [ ] **Step 1: Run all pure tests** `python -m pytest shenai_health_scan/tests -v` → all PASS.
- [ ] **Step 2: Demo smoke** `python -m shenai_health_scan.demo --source 0` → reaches DONE.
- [ ] **Step 3: Commit** any fixes.

---

## Deployment: run as a robot service on PC2 (auto-start on boot)

> Do this on the robot's **PC2** (Jetson Orin NX, arm64). **Never PC1.** Persist files under `$HOME = /agibot/data/home/agi` (non-volatile), avoiding `$HOME/aimdk*`.

### D1. Place the code and the arm64 SDK
```bash
# On PC2:
mkdir -p /agibot/data/home/agi/x2_ws/src
cd /agibot/data/home/agi/x2_ws/src
git clone https://github.com/nerrazzuri/shen_ai_integration.git
# Copy the ROS package into the workspace src (or symlink):
cp -r shen_ai_integration/shenai_health_scan .
# Vendor the arm64 Shen.AI SDK (NOT in git):
#   unzip shenai-sdk-python-linux-arm64.zip into /agibot/data/home/agi/shenai_sdk_pkg
#   so that /agibot/data/home/agi/shenai_sdk_pkg/shenai_sdk/ exists.
```

### D2. Build the workspace
```bash
cd /agibot/data/home/agi/x2_ws
# aimdk_msgs must be available (from the X2 SDK). Build it too if not already installed.
colcon build --packages-select aimdk_msgs shenai_health_scan
source install/setup.bash
pip install --user requests   # if not present
```

### D3. Configure secrets and endpoint
```bash
# Put the API key + third-party endpoint into params or an env file.
# Recommended: an env file the service loads (keeps secrets out of git):
cat > /agibot/data/home/agi/shenai.env <<'EOF'
SHENAI_API_KEY=your_real_key_here
SHENAI_PUBLISH_ENDPOINT=https://thirdparty.example.com/api/results
SHENAI_PUBLISH_AUTH=Bearer xxxxx
PYTHONPATH=/agibot/data/home/agi/shenai_sdk_pkg
EOF
# Edit config/params.yaml (installed under install/share/...) OR pass overrides via launch.
# Simplest for MVP: set api_key/publisher.endpoint directly in params.yaml before colcon build.
```

### D4. Create a wrapper launch script
```bash
cat > /agibot/data/home/agi/run_shenai_scan.sh <<'EOF'
#!/usr/bin/env bash
set -e
source /opt/ros/humble/setup.bash
source /agibot/data/home/agi/x2_ws/install/setup.bash
set -a; source /agibot/data/home/agi/shenai.env; set +a
exec ros2 launch shenai_health_scan shenai_health_scan.launch.py
EOF
chmod +x /agibot/data/home/agi/run_shenai_scan.sh
```

### D5. Install a systemd service (auto-start on boot)
```bash
sudo tee /etc/systemd/system/shenai-health-scan.service >/dev/null <<'EOF'
[Unit]
Description=Shen.AI Health Scan (AgiBot X2)
After=network-online.target
Wants=network-online.target
# If the robot exposes a ROS/HAL readiness target, add it to After= as well.

[Service]
Type=simple
User=agi
ExecStart=/agibot/data/home/agi/run_shenai_scan.sh
Restart=on-failure
RestartSec=5
# Give camera/HAL time to come up before first scan attempts:
TimeoutStartSec=60

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable shenai-health-scan.service
sudo systemctl start shenai-health-scan.service
```

### D6. Verify the service
```bash
systemctl status shenai-health-scan.service
journalctl -u shenai-health-scan.service -f          # watch logs
# Trigger a scan manually:
source /opt/ros/humble/setup.bash
source /agibot/data/home/agi/x2_ws/install/setup.bash
ros2 service call /shenai_health_scan/start_scan std_srvs/srv/Trigger {}
# Or double-pat the robot's head if 'touch' trigger is enabled.
```

### D7. Validate the frame-rate risk first
Before relying on results, confirm the camera actually delivers >= submit_fps:
```bash
ros2 topic hz /aima/hal/sensor/rgbd_head_front/rgb_image
```
If `< 30 Hz`, change `camera_topic` to a higher-rate source (e.g. a stereo topic) or request a higher publish rate, then rebuild. This was design risk #1.

---

## Self-review (against the spec)

- **Camera → BGR → Shen.AI:** RosCamera (T12) + ShenAiEngine.submit (T11) + 30 Hz loop (T9). ✓
- **Guided state machine + TTS/face screen:** Orchestrator (T2) + RosIO (T13). ✓
- **Vitals on face screen:** cards.py (T6) + RosIO.show result_card (T13). ✓
- **Full payload to third-party API:** ResultsPublisher (T5) + loop `_enrich` (T9). ✓
- **Pluggable triggers (any robot input):** base + Manual/Service/Touch/Topic (T8, T14); add one class to extend. ✓
- **Online licensing:** ScanConfig.offline=False (T3), ShenAiEngine init (T11). ✓
- **Runs on PC2 / arm64:** packaging (T16) + deployment D1–D6. ✓
- **Off-robot runnable MVP:** FakeCamera + MockEngine + ConsoleIO + demo (T7, T4, T6, T10). ✓
- **Frame-rate risk handled:** measured_fps + D7 validation. ✓
- **Graceful failure (no face / bad signal / publisher down):** orchestrator FAILED paths (T2), dead-letter (T5), best-effort RobotIO (T13). ✓

**Placeholder scan:** the only deferred concrete value is the third-party API schema/URL and the exact Shen.AI enum member names — both flagged with explicit verification steps (T3 note, T11 Step 2, T13 open item), not silent gaps.
