from shenai_health_scan.core.types import FaceHint
from shenai_health_scan.engine.shenai_engine import ShenAiEngine


def test_too_close_face_state_maps_to_too_close_hint():
    class FaceState:
        NOT_VISIBLE = object()
        TOO_FAR = object()
        TOO_CLOSE = object()
        NOT_CENTERED = object()
        TURNED_AWAY = object()

    engine = ShenAiEngine.__new__(ShenAiEngine)
    engine._FaceState = FaceState

    assert engine._hint(FaceState.TOO_CLOSE, is_ready=False) == FaceHint.TOO_CLOSE
