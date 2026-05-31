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
