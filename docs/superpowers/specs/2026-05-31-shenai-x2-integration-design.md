# Shen.AI Health Scan on AgiBot X2 — Integration Design

**Date:** 2026-05-31
**Status:** Approved design (implementation plan to follow)
**Author:** Liang Kai Feng (with Claude)

## 1. Purpose

Integrate Shen.AI's contactless facial health-scan (rPPG) capability into the
AgiBot X2 humanoid robot, using the robot's **own camera** as the video source.
The robot conducts a guided scan (speaking and showing instructions), displays
**vitals on its face screen**, and forwards the **full result payload to a
third-party application via an API** for that app to consume.

## 2. Context & key findings

Two SDKs were studied directly from their packages, not assumptions:

### Shen.AI — `shenai-sdk-python-linux-arm64` (v3.0.9-beta.1)
- Pure-Python package wrapping a native `libShenaiSDK.so` via `ctypes`.
  Ships the **arm64** Linux build — matches the X2 dev unit CPU.
- **Push model.** The app supplies frames; there is no internal camera capture.
  Core lifecycle (from `shenai_sdk/client.py`):
  - `ShenaiSDK(api_key, user_id=None, offline=True, language="auto")`
  - `precision_mode`, `measurement_preset`, `set_custom_measurement_config(...)`
  - `start_measurement()` / `stop_measurement()` / `reset_measurement_session()`
  - `submit_frame(data, width, height, stride_bytes=None, timestamp_ns=-1, pixel_format=PixelFormat.BGR24)`
    — expects **BGR24**; prefers **uniform >= 30 fps**; `timestamp_ns` should be a
    monotonic capture timestamp.
  - Polling: `get_face_state()`, `get_face_bbox()`, `get_face_pose()`,
    `is_ready_to_start_measurement()`, `get_progress_percent()`,
    `get_measurement_state()`, `get_current_signal_quality_metric()`,
    `get_total_bad_signal_seconds()`.
  - Realtime: `get_realtime_metrics(period_sec)`, `get_realtime_heart_rate()`, etc.
  - Final: `get_measurement_results()`, `get_measurement_results_with_heartbeats()`,
    `get_health_risks()`, `compute_health_risks(factors)`.
  - Export: `get_result_as_fhir_observation()`, `send_result_fhir_observation(url)`,
    PDF helpers, `get_measurement_id()`, `get_trace_id()`.
- **Licensing:** initialized with an API key/token. `offline=False` validates
  licensing over the internet (our chosen mode — robot has connectivity).

### AgiBot X2 — `lx2501_3-v0.9.0.4` AimDK
- **ROS 2** robot SDK (C++ and Python `rclpy`); messages/services under
  `aimdk_msgs`; rich `py_examples`.
- **Cameras as ROS 2 topics**, e.g.
  `/aima/hal/sensor/rgbd_head_front/rgb_image` (`sensor_msgs/Image`),
  plus compressed, depth, stereo (`stereo_head_front_left/...`), head-rear.
  `take_photo.py` shows `cv_bridge` converting a ROS `Image` to OpenCV BGR.
- **Output channels:** face screen (`PlayVideo`, `PlayMediaFile`, `PlayEmoji`),
  TTS (`PlayTts`), lights, plus head **touch sensor** (`echo_head_touch_sensor`).
- **Onboard compute (validated against AgiBot docs):**
  - Development Computing Unit **PC2 = Jetson Orin NX**, 8-core Arm Cortex-A78AE
    (**arm64**), Ampere GPU, 16 GB RAM, 512 GB. Developer code/ROS 2 nodes run here.
  - PC1 (motion control) is **off-limits** for secondary development.
  - RGB-D head camera (Gemini 335): color up to **1920x1080 @ up to 60 fps**.
  - Front stereo: up to 2064x1552 @ 40 fps.

### Fit summary
arm64 SDK ↔ arm64 PC2; Python ↔ Python (`rclpy`); camera fps capacity exceeds
the >= 30 fps rPPG requirement; BGR conversion already demonstrated in examples.
The integration is a **single in-process ROS 2 Python node** — no browser, no
WebRTC bridge, no cross-language IPC.

## 3. Scope

**In scope**
- One ROS 2 Python node on PC2 that runs a guided facial health scan from the
  robot camera, shows vitals on the face screen, speaks guidance via TTS, and
  POSTs the full result payload to a configurable third-party API.
- Pluggable scan-trigger layer (any robot input can start a scan).

**Out of scope (for now)**
- The third-party app itself and its exact API schema (designed as a pluggable
  contract with a placeholder endpoint until provided).
- Per-person demographic data entry for full cardiovascular risk scoring (the
  pipeline supports it; UX for collecting it is deferred).
- Multi-process / multi-robot scaling (documented as a future "Approach C").

## 4. Architecture

Approach **B — one process, cleanly decomposed**. Single ROS 2 node, internally
split into focused components with clear interfaces, three threads with explicit
hand-offs to protect rPPG frame timing.

```
                         ROS 2 (PC2, Jetson Orin NX, arm64)
 +----------------------------------------------------------------------+
 |  [Camera topic] /aima/hal/sensor/rgbd_head_front/rgb_image           |
 |        | rgb8 Image (cv_bridge -> BGR)                                |
 |        v                                                             |
 |  +--------------+   latest-frame    +---------------------------+    |
 |  | CameraSource | - (1 slot, lock) -> Measurement loop (30 Hz)   |    |
 |  | (ROS cb thr) |                   |  - ShenAiEngine.submit     |    |
 |  +--------------+                   |  - poll face/progress      |    |
 |                                     |  - drive ScanOrchestrator  |    |
 |                                     +-----------+----------------+    |
 |                            +--------------------+----------------+    |
 |                            v                                     v    |
 |                   +-----------------+              +--------------------+
 |                   |     RobotIO     |              |  ResultsPublisher  |
 |                   | PlayTts + face  |              | queue -> worker    |
 |                   | screen (vitals) |              | thread -> HTTP POST|
 |                   +-----------------+              +--------------------+
 +----------------------------------------------------------------------+
```

### Threading model (core of Approach B)
- **Camera callback thread** (ROS executor): converts each ROS `Image` to BGR
  and writes it into a single-slot, lock-guarded "latest frame" buffer. Never
  blocks on the SDK or the network.
- **Measurement loop** (dedicated thread, fixed >= 30 Hz cadence): pulls the
  latest frame, calls `ShenAiEngine.submit_frame(...)` with a monotonic
  timestamp, polls SDK state, advances `ScanOrchestrator`. **Only thread that
  touches the SDK context** (single-owner).
- **ResultsPublisher worker thread**: drains a queue and performs the
  third-party HTTP POST. A slow/failed POST cannot stall frames or the UI.
- `RobotIO` is invoked from the measurement loop but issues only async ROS
  service calls, so it is non-blocking.

**Why a fixed-rate loop (not submit-from-camera-callback):** Shen.AI wants
uniform >= 30 fps. Decoupling submission from a jittery/possibly sub-30 Hz camera
publish rate via latest-frame buffer + fixed cadence yields uniform timing and
lets us detect a too-slow camera explicitly instead of silently feeding bad data.

## 5. Components

Each component has one responsibility and a small interface (final signatures in
the implementation plan; contracts fixed here).

### 5.1 `CameraSource` — ROS 2 subscription -> BGR frames
- `start()` / `stop()`
- `get_latest() -> (frame_bgr, width, height, stride, capture_ts_ns) | None`
  (single slot, lock-guarded, newest wins, stale dropped)
- `measured_fps` for the loop's startup health check
- Config: `topic`, `encoding`; converts rgb8 -> BGR via `cv_bridge`
  (as in `take_photo.py`)

### 5.2 `ShenAiEngine` — sole owner of the SDK context
- `__init__(api_key, offline=False, preset, precision_mode)`
- `begin_session()` (-> `reset_measurement_session()`), `start()`
  (-> `start_measurement()`), `stop()`
- `submit(frame_bgr, w, h, stride, ts_ns)`
- `poll() -> EnginePoll` (bundles `face_state`, `is_ready`, `progress`,
  realtime metrics, `measurement_state`, signal quality)
- `final_results() -> MeasurementResults | None`,
  `health_risks(factors) -> HealthRisks`
- `close()` / `destroy_runtime()`

### 5.3 `ScanOrchestrator` — pure state machine (no ROS/SDK calls directly)
- `request_scan()` — thread-safe entry point the trigger layer calls
- `on_tick(poll: EnginePoll, now) -> list[Effect]`, where `Effect` is a typed
  intent: `Speak(text)`, `ShowScreen(view, data)`, `EngineCmd(start|stop|reset)`,
  `PublishResults(payload)`. The measurement loop executes effects against the
  engine, `RobotIO`, and `ResultsPublisher`.
- Fully unit-testable with synthetic `EnginePoll` sequences; zero hardware.

### 5.4 `RobotIO` — robot-facing output adapter
- `speak(text, priority)` -> `PlayTts` (async)
- `show(view, data)` -> face screen via `PlayVideo` / `PlayMediaFile` /
  `PlayEmoji`; `view` in {idle, coaching, measuring, result_card, error}
- Non-blocking; logs and swallows ROS service failures (UI is best-effort)

### 5.5 `ResultsPublisher` — third-party forwarder (isolated thread)
- `publish(payload: dict)` — enqueue, return immediately
- Worker thread POSTs JSON to configurable `endpoint` + `auth`; retry/backoff;
  dead-letters to a local file on persistent failure
- Optional FHIR emission via `get_result_as_fhir_observation()`
- Payload contract documented below; placeholder until the real schema is supplied

### 5.6 Pluggable trigger layer — `ScanTrigger`
A common interface so **any** robot input can start a scan, now or later:
```python
class ScanTrigger(Protocol):
    def start(self, on_trigger: Callable[[], None]) -> None: ...
    def stop(self) -> None: ...
```
- Each trigger runs independently and calls `orchestrator.request_scan()` via the
  shared `on_trigger` callback. Multiple may be active at once; config selects
  which are enabled.
- Triggers spec'd: `ServiceTrigger` (ROS `~/start_scan`, always-on baseline),
  `TouchTrigger` (head touch sensor), `VoiceTrigger` (wake word / interaction
  intent), `TopicTrigger` (generic ROS topic).
- Adding a new robot trigger later = one new class implementing `ScanTrigger`,
  registered in config. No changes to the orchestrator or loop.

## 6. Scan lifecycle (state machine + UX)

| State | Entry trigger | Shen.AI / robot action | Face screen | TTS |
|---|---|---|---|---|
| **Idle** | node start | camera loop running, not submitting | branding / "Ready" | - |
| **Triggered** | a `ScanTrigger` fires | `reset_measurement_session()`, begin submitting | "Starting health scan..." | "Let's check your vitals. Please look at my eyes." |
| **AcquireFace** | submitting started | poll `face_state`/`face_bbox`/`is_ready` | live face-guide overlay | dynamic: "Come closer", "Hold still", "Good - stay there" |
| **Measuring** | `is_ready` + face OK -> `start_measurement()` | poll `progress`, realtime metrics | live vitals + progress ring | "Measuring, please hold still" + periodic reassurance |
| **Done** | `measurement_state == FINISHED` | `get_measurement_results()` (+ risks if available) -> RobotIO **and** ResultsPublisher | final vitals card | "All done. Your heart rate is ..." |
| **Failed/Aborted** | timeout / face lost / `FAILED` / bad signal | `stop_measurement()`, optional retry | error/retry view | "I couldn't get a clear reading. Let's try again." |

- **Face coaching:** `AcquireFace` maps `FaceState` + normalized bbox into a small
  set of spoken/visual hints (too far / off-centre / not ready / ready). This is
  what makes the robot feel like it is actively conducting the scan.
- **Output split (requirement):** face screen shows **vitals** (HR, HRV,
  breathing rate, stress, blood pressure) live + final card; `ResultsPublisher`
  sends the **full payload** (all vitals + quality metrics + `measurement_id` /
  `trace_id` + health risks if computed) to the third-party app.
- **Guards:** configurable `acquire_face_timeout`, `max_measure_seconds`, and a
  `min_signal_quality` / `get_total_bad_signal_seconds()` threshold to fail
  gracefully instead of returning garbage.

## 7. Configuration

Single ROS 2 params file / launch args (mirroring `example.launch.py`):
- **Shen.AI:** `api_key`, `offline=false`, `measurement_preset`, `precision_mode`,
  optional `custom_measurement_config`
- **Camera:** `topic` (default `/aima/hal/sensor/rgbd_head_front/rgb_image`),
  `submit_fps` (default 30)
- **Triggers:** `enabled_triggers: [service, touch, voice, topic]` + per-trigger params
- **Publisher:** `endpoint`, `auth_header`, `timeout`, `retry`, `dead_letter_path`,
  `enable_fhir`
- **Guards:** `acquire_face_timeout`, `max_measure_seconds`, `min_signal_quality`
- **Library discovery:** `PYTHONPATH` to `shenai_sdk/` (ships `libShenaiSDK.so`),
  or `SHENAI_SDK_LIB`

### Third-party results payload (placeholder contract)
```json
{
  "measurement_id": "string",
  "trace_id": "string",
  "timestamp": "ISO-8601",
  "vitals": {
    "heart_rate_bpm": 0,
    "hrv_sdnn_ms": 0,
    "breathing_rate_bpm": 0,
    "stress_index": 0,
    "systolic_bp_mmhg": 0,
    "diastolic_bp_mmhg": 0
  },
  "quality": { "average_signal_quality": 0, "bad_signal_seconds": 0 },
  "health_risks": { "...": "present only if demographics supplied" }
}
```
Exact field names/auth to be reconciled with the third-party app when available.

## 8. Risks & mitigations

1. **Camera frame rate (highest risk).** rPPG needs uniform >= 30 fps; the X2
   example's RGB-D topic hinted at lower publish rates than the sensor's 60 fps
   capacity.
   - Measure actual topic Hz on startup (~2 s); log/warn if `< submit_fps`.
   - Prefer the camera/profile delivering >= 30 fps (RGB-D color up to 60, stereo
     up to 40), selectable via `topic`.
   - Fixed-cadence loop re-submits the latest buffered frame for uniform timing;
     if true capture rate is too low, fail the scan with a clear message rather
     than return a bad reading.
   - **On-device fps validation is the first implementation step**, before UX.
2. **Licensing / connectivity (online mode).** `LicenseInvalidError` /
   `ConnectionError` at init -> log + "service unavailable"; never crash mid-scan.
3. **Camera dropout.** No fresh frame for N ms -> pause/abort with spoken retry.
4. **No face / bad signal.** Timeouts + `min_signal_quality` -> `Failed` + retry.
5. **RobotIO failures.** Logged and swallowed; UI is best-effort.
6. **Publisher failures.** Retry/backoff then dead-letter to disk; the local
   scan still succeeds on the face screen.
7. **Face-screen API mismatch.** Exact `PlayVideo`/`PlayMediaFile` rendering
   capabilities (custom dynamic content vs. preset media) need confirmation on
   device; `RobotIO` isolates this behind `show(view, data)` so the rendering
   strategy can change without touching the rest.

## 9. Testing strategy (off-robot first, TDD-friendly)

- **`ScanOrchestrator`** (pure) -> unit tests drive Idle -> ... -> Done/Failed
  with synthetic `EnginePoll` sequences; zero hardware.
- **`ShenAiEngine`** tested against the **real `.so`** by feeding frames from a
  recorded video / laptop webcam (SDK takes arbitrary frames, per
  `quickstart.py`). Validates licensing, `submit_frame`, results plumbing on a
  dev box (x64 SDK build for laptop; arm64 on robot).
- **`CameraSource`, `RobotIO`, triggers** behind interfaces -> fakes in tests; a
  `FakeCameraSource` replays a video file so the whole pipeline runs end-to-end
  without the robot.
- **`ResultsPublisher`** -> local mock HTTP server; assert payload schema +
  retry/dead-letter behavior.
- **Integration on PC2 last:** real camera topic, real face screen/TTS, real
  third-party endpoint (or sandbox).

## 10. Deployment

- A ROS 2 `ament_python` package dropped beside `py_examples`, run via
  `ros2 run` / launch file on **PC2** (never PC1).
- `shenai_sdk/` + `libShenaiSDK.so` vendored into the package or on `PYTHONPATH`.
- Results / dead-letters written under `$HOME` (non-volatile per the X2 README;
  avoid `$HOME/aimdk*`).

## 11. Future direction (Approach C)

If the scanner must be reused by other robot apps, split into separate ROS 2
nodes (scanner / interaction / forwarder) communicating over topics/services.
The current component boundaries (esp. the typed `Effect` outputs and the
trigger/output interfaces) make that migration mechanical.
