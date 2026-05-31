# Continuation / Handoff Notes

Pick-up notes for resuming this project on the **Ubuntu 22.04 LTS workstation**.
Chat history does not transfer between machines — **this file + the spec + the
plan are the source of truth.** Read them in this order:

1. `docs/superpowers/specs/2026-05-31-shenai-x2-integration-design.md` — the approved design
2. `docs/superpowers/plans/2026-05-31-shenai-x2-mvp.md` — the executable implementation plan (TDD, task-by-task)
3. This file — current state, decisions, environment setup, next action

---

## Where we are (as of 2026-05-31)

- **Phase:** design + plan complete and approved. **No source code written yet.**
- **Done:** studied both SDKs from their actual packages; produced approved design
  (Approach B); wrote the full TDD implementation plan with deployment-as-systemd-service.
- **Next action:** execute the plan starting at **Task 0** (scaffold the
  `shenai_health_scan` ROS 2 package), proceeding through Tasks 1–17, then the
  Deployment section on the robot.

## How to resume with Claude on the Linux box

```bash
git clone https://github.com/nerrazzuri/shen_ai_integration.git
cd shen_ai_integration
# then start Claude Code here and say:
#   "Read CONTINUATION.md, the spec, and the plan, then execute the
#    implementation plan starting at Task 0 using TDD."
```
The repo carries the superpowers plugin enablement (`.claude/settings.json`),
the design spec, and the plan, so the workflow continues seamlessly.

## Decisions already locked (do not re-litigate)

- **Architecture:** Approach B — one in-process ROS 2 Python node, decomposed into
  CameraSource / ShenAiEngine / ScanOrchestrator / RobotIO / ResultsPublisher +
  pluggable ScanTrigger layer. Three threads (camera cb / fixed-rate measurement
  loop / publisher worker).
- **Runs on:** robot **PC2** dev unit (Jetson Orin NX, **arm64**, ROS 2 Humble).
  Never PC1 (motion control — prohibited for dev).
- **UX:** robot-native — TTS (`PlayTts`) + face screen (`PlayVideo`).
- **Outputs:** vitals on the **face screen**; **full payload POSTed to a
  third-party app API**.
- **Licensing:** have API key, **online** mode (`offline=False`).
- **Trigger:** fully pluggable (`ScanTrigger`); ROS service is the baseline,
  touch/voice/topic are configurable add-ons.

## Environment: workstation vs robot (IMPORTANT)

| | Ubuntu 22.04 workstation (x86_64) | Robot PC2 (Jetson, arm64) |
|---|---|---|
| Shen.AI SDK | **download the x64 headless Python build** from developer.shen.ai | use `shenai-sdk-python-linux-arm64` (already have the zip) |
| ROS 2 | install **Humble** (matches robot) | Humble (pre-installed) |
| `.so` | arm64 `.so` will **not** load here — must use x64 build | arm64 build |
| Use | unit tests + off-robot demo (`scan_demo`, webcam) | full node (`scan_node`) |

### Workstation setup checklist
```bash
# ROS 2 Humble: follow docs.ros.org Humble Ubuntu install (ros-humble-desktop)
sudo apt install ros-humble-desktop python3-colcon-common-extensions \
                 ros-humble-cv-bridge python3-opencv
pip install --user pytest requests numpy

# Shen.AI x64 SDK: download from developer.shen.ai (Linux headless Python, x64),
# unzip somewhere, then:
export PYTHONPATH=/path/to/shenai-sdk-python-linux-x64:$PYTHONPATH
# (or export SHENAI_SDK_LIB=/path/to/libShenaiSDK.so)

# aimdk_msgs: copy lx2501_3-v0.9.0.4/src/aimdk_msgs into your ROS 2 workspace src/
# and `colcon build --packages-select aimdk_msgs` so ROS adapters/tests can import it.
```

## Vendor SDK files (git-ignored — must be re-obtained, not in the repo)

These are **not** in git (size + licensing). On Windows they currently live in
`d:\Projects\shen_ai_integration\` and are extracted under `_extracted/`:
- `shenai-sdk-python-linux-arm64.zip` — robot SDK (keep for PC2 deployment)
- `shenai-sdk-web.zip` — reference only, **not used**
- `lx2501_3-v0.9.0.4.zip` — AgiBot X2 AimDK (ROS 2 SDK, `aimdk_msgs`, examples, docs)

Action on the Linux box: copy these zips over (USB/cloud) OR re-download the
**x64** Shen.AI build for local dev + keep the **arm64** build for the robot.
Then place `aimdk_msgs` in the ROS 2 workspace.

## Key verified API facts (already confirmed from the packages)

See the plan's "Verified interface facts" section. Highlights:
- Shen.AI: `submit_frame(data, w, h, stride_bytes, timestamp_ns, pixel_format=BGR24)`;
  push model; `offline=False` for online licensing.
- Camera topic: `/aima/hal/sensor/rgbd_head_front/rgb_image` (rgb8 → BGR via cv_bridge).
- TTS srv `/aimdk_5Fmsgs/srv/PlayTts`; face screen srv `/face_ui_proxy/play_video`;
  touch topic `/aima/hal/sensor/touch_head` (`PAT_ONCE/TWICE/TRIPLE`).

## Open items to resolve during/after implementation

1. **Third-party API contract** — real URL, auth, and payload schema. Publisher is
   built pluggable with a placeholder until provided.
2. **Shen.AI enum member names** — verify `MeasurementPreset`/`PrecisionMode`/
   `FaceState`/`MeasurementState` identifiers against `shenai_sdk/enums.py` on the
   x64 SDK; adjust `getattr` names in `shenai_engine.py` if different.
3. **Face-screen rendering** — confirm whether `PlayVideo` accepts a still PNG or
   requires video; if video-only, render a short MP4 in `cards.py`.
4. **Camera frame rate (design risk #1)** — `ros2 topic hz` on the camera topic;
   must be ≥ 30 Hz or pick a higher-rate source. Validate before trusting results.

## Repo layout

```
docs/superpowers/specs/2026-05-31-shenai-x2-integration-design.md   # design
docs/superpowers/plans/2026-05-31-shenai-x2-mvp.md                  # implementation plan
CONTINUATION.md   # this file
README.md
CLAUDE.md         # engineering guidelines
.gitignore        # excludes vendor zips/binaries/secrets
.claude/settings.json
# shenai_health_scan/  <-- to be created at Task 0
```
