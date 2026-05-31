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
