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

class IncrementingFrameCam:
    def __init__(self):
        self._ts = 0

    def start(self): pass
    def stop(self): pass
    def get_latest(self):
        self._ts += 1
        return (b"\x00", 1, 1, 3, self._ts)
    @property
    def measured_fps(self): return 30.0

class CountingEngine(MockEngine):
    def __init__(self):
        super().__init__()
        self.submitted_ts = []
        self.poll_count = 0
        self.reset_count = 0

    def begin_session(self):
        self.reset_count += 1
        super().begin_session()

    def submit(self, data, width, height, stride, ts_ns):
        self.submitted_ts.append(ts_ns)
        super().submit(data, width, height, stride, ts_ns)

    def poll(self):
        self.poll_count += 1
        return super().poll()

def test_loop_runs_full_scan_to_done():
    eng = MockEngine(face_after=1, ready_after=2, finish_after=4)
    orch = ScanOrchestrator()
    io, pub = RecIO(), RecPub()
    loop = MeasurementLoop(IncrementingFrameCam(), eng, orch, io, pub, submit_fps=30)
    orch.request_scan()
    for i in range(10):
        loop.tick_once(now=float(i))
    assert orch.state == ScanState.DONE
    assert any("done" in s.lower() for s in io.spoken)
    assert len(pub.payloads) == 1
    assert "measurement_id" in pub.payloads[0]

def test_loop_does_not_resubmit_same_frame_timestamp():
    eng = CountingEngine()
    orch = ScanOrchestrator()
    loop = MeasurementLoop(OneFrameCam(), eng, orch,
                           RecIO(), RecPub(), submit_fps=30)

    orch.request_scan()
    loop.tick_once(now=1.0)
    loop.tick_once(now=2.0)
    loop.tick_once(now=3.0)

    assert eng.submitted_ts == [1]

def test_loop_does_not_feed_engine_while_idle():
    eng = CountingEngine()
    loop = MeasurementLoop(IncrementingFrameCam(), eng, ScanOrchestrator(),
                           RecIO(), RecPub(), submit_fps=30)

    loop.tick_once(now=1.0)
    loop.tick_once(now=2.0)

    assert eng.submitted_ts == []
    assert eng.poll_count == 0

def test_loop_resets_engine_before_first_scan_frame():
    eng = CountingEngine()
    orch = ScanOrchestrator()
    loop = MeasurementLoop(IncrementingFrameCam(), eng, orch,
                           RecIO(), RecPub(), submit_fps=30)

    orch.request_scan()
    loop.tick_once(now=1.0)

    assert eng.reset_count == 1
    assert eng.submitted_ts == []
    assert orch.state == ScanState.ACQUIRE_FACE
