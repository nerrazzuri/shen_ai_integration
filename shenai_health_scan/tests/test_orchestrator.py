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

def test_acquire_face_prompts_user_to_move_back_when_too_close():
    o = ScanOrchestrator()
    o.request_scan(); o.on_tick(mk(face_present=False), now=0.0)

    effects = o.on_tick(mk(face_hint=FaceHint.TOO_CLOSE), now=1.0)

    assert any(isinstance(e, Speak) and "move back" in e.text.lower()
               for e in effects)

def test_measuring_prompts_to_hold_position_every_three_seconds():
    o = ScanOrchestrator()
    o.request_scan(); o.on_tick(mk(), now=0.0)
    o.on_tick(mk(is_ready=True), now=1.0)  # -> MEASURING

    effects = o.on_tick(mk(progress=0.2), now=3.0)
    assert not any(isinstance(e, Speak) for e in effects)

    effects = o.on_tick(mk(progress=0.3), now=4.1)
    assert any(isinstance(e, Speak) and "hold" in e.text.lower()
               for e in effects)

    effects = o.on_tick(mk(progress=0.4), now=5.0)
    assert not any(isinstance(e, Speak) for e in effects)

    effects = o.on_tick(mk(progress=0.5), now=7.2)
    assert any(isinstance(e, Speak) and "hold" in e.text.lower()
               for e in effects)

def test_measuring_finishes_and_publishes():
    o = ScanOrchestrator()
    o.request_scan(); o.on_tick(mk(), now=0.0)
    o.on_tick(mk(is_ready=True), now=1.0)  # -> MEASURING
    v = Vitals(heart_rate_bpm=72, systolic_bp_mmhg=120, diastolic_bp_mmhg=80)
    effects = o.on_tick(mk(finished=True, vitals=v), now=2.0)
    assert o.state == ScanState.DONE
    assert isinstance(effects[0], ShowScreen)
    assert effects[0].view == "processing_results"
    assert any(isinstance(e, Speak) and "scan complete" in e.text.lower()
               for e in effects)
    assert any(isinstance(e, Speak) and "wait" in e.text.lower()
               for e in effects)
    assert any(isinstance(e, ShowScreen) and e.view == "result_card" for e in effects)
    assert any(isinstance(e, PublishResults) for e in effects)

def test_measuring_engine_failure_fails():
    o = ScanOrchestrator(max_measure_seconds=60, min_signal_quality=0.3)
    o.request_scan(); o.on_tick(mk(), now=0.0); o.on_tick(mk(is_ready=True), now=1.0)
    effects = o.on_tick(mk(failed=True), now=3.0)
    assert o.state == ScanState.FAILED

def test_measuring_low_signal_quality_fails():
    o = ScanOrchestrator(min_signal_quality=0.5)
    o.request_scan(); o.on_tick(mk(), now=0.0); o.on_tick(mk(is_ready=True), now=1.0)
    v = Vitals(heart_rate_bpm=72)
    effects = o.on_tick(mk(finished=True, vitals=v, signal_quality=0.2), now=2.0)
    assert o.state == ScanState.FAILED
    assert not any(isinstance(e, PublishResults) for e in effects)

def test_measuring_finishes_when_quality_meets_threshold():
    o = ScanOrchestrator(min_signal_quality=0.5)
    o.request_scan(); o.on_tick(mk(), now=0.0); o.on_tick(mk(is_ready=True), now=1.0)
    v = Vitals(heart_rate_bpm=72)
    effects = o.on_tick(mk(finished=True, vitals=v, signal_quality=0.9), now=2.0)
    assert o.state == ScanState.DONE
    assert any(isinstance(e, PublishResults) for e in effects)
