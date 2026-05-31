from shenai_health_scan.engine.mock_engine import MockEngine
from shenai_health_scan.core.types import FaceHint

def feed(engine, n):
    for _ in range(n):
        engine.submit(b"\x00", 1, 1, 3, -1)
    return engine.poll()

def test_progression():
    e = MockEngine(face_after=2, ready_after=4, finish_after=8)
    e.begin_session()
    p = feed(e, 1); assert p.face_present is False
    p = feed(e, 3); assert p.face_present is True and p.is_ready is False
    e.start()
    p = feed(e, 4); assert p.is_ready is True
    p = feed(e, 5); assert p.finished is True and p.vitals.heart_rate_bpm == 72
    r = e.final_results()
    assert r.heart_rate_bpm == 72
