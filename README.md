# Shen.AI Health Scan on AgiBot X2

Integrate Shen.AI's contactless facial health-scan (rPPG) into the AgiBot X2
humanoid robot, using the robot's own camera. The robot runs a guided scan
(TTS + face screen), shows **vitals on its face screen**, and forwards the
**full result payload to a third-party app via an API**.

> **Status:** design phase. The approved design lives in
> [`docs/superpowers/specs/2026-05-31-shenai-x2-integration-design.md`](docs/superpowers/specs/2026-05-31-shenai-x2-integration-design.md).
> No implementation code yet.

## How it works (summary)

A single ROS 2 Python node on the X2 **PC2** dev unit (Jetson Orin NX, arm64):

- subscribes to a robot camera topic (`sensor_msgs/Image`), converts to BGR;
- feeds frames to the **Shen.AI headless arm64 Python SDK** at >= 30 fps
  (`submit_frame`);
- runs a guided state machine (acquire face -> measure -> done) with TTS +
  face-screen coaching;
- shows vitals on the face screen and POSTs the full result set to a
  configurable third-party endpoint.

See the design doc for the full architecture, threading model, components,
pluggable trigger layer, risks, and testing strategy.

## Vendor SDKs (not in this repo)

These third-party packages are **git-ignored** (size + licensing) and must be
obtained from their vendors and placed locally:

| SDK | Package | Notes |
|---|---|---|
| Shen.AI (target) | `shenai-sdk-python-linux-arm64` | headless arm64 Python + `libShenaiSDK.so`; runs on PC2 |
| Shen.AI (web) | `shenai-sdk-web` | reference only; not used in this integration |
| AgiBot X2 AimDK | `lx2501_3-v0.9.0.4` | ROS 2 SDK, `aimdk_msgs`, examples, docs |

Shen.AI docs: <https://developer.shen.ai/> ·
AgiBot X2 docs: <https://x2-aimdk.agibot.com/>

## Repository layout

```
docs/superpowers/specs/   # approved design / spec documents
CLAUDE.md                 # engineering guidelines for this project
README.md
.gitignore
```

## Requirements (target runtime)

- AgiBot X2 PC2 dev unit (Jetson Orin NX, arm64, Ubuntu + ROS 2)
- Python 3.8+, `rclpy`, `cv_bridge`, OpenCV
- Shen.AI arm64 Python SDK + a valid Shen.AI API key (online licensing)
