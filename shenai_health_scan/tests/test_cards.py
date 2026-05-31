import numpy as np
from shenai_health_scan.robot_io.cards import render_result_card

def test_render_returns_png_bytes():
    png = render_result_card({"heart_rate_bpm": 72, "systolic_bp_mmhg": 120,
                              "diastolic_bp_mmhg": 80})
    assert isinstance(png, (bytes, bytearray)) and png[:8] == b"\x89PNG\r\n\x1a\n"
