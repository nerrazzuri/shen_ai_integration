from shenai_health_scan.engine.debug import DebugEngineProxy
from shenai_health_scan.engine.mock_engine import MockEngine


def test_debug_proxy_logs_engine_status_once_per_interval():
    lines = []

    class Engine(MockEngine):
        def debug_status(self):
            return {
                "face_state": "NOT_CENTERED",
                "measurement_state": "WAITING_FOR_FACE",
                "ready": False,
                "bbox": {"x": 0.45, "y": 0.2, "width": 0.2, "height": 0.4},
                "pose": {"yaw": 1.0, "pitch": -2.0, "roll": 0.5},
            }

    engine = DebugEngineProxy(
        Engine(),
        emit=lines.append,
        now=lambda: 10.0,
        camera_fps=lambda: 29.5,
        interval_sec=1.0,
    )

    engine.poll()

    assert len(lines) == 1
    assert "face_state=NOT_CENTERED" in lines[0]
    assert "vitals=missing" in lines[0]
    assert "bbox=(cx=0.55, cy=0.40, w=0.20, h=0.40)" in lines[0]
    assert "pose=(yaw=1.0, pitch=-2.0, roll=0.5)" in lines[0]
    assert "camera_fps=29.5" in lines[0]
