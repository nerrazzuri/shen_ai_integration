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
