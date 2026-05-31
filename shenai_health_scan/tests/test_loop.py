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
