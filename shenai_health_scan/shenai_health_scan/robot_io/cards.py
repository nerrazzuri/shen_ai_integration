from __future__ import annotations
from typing import Dict, Any
import cv2
import numpy as np

_LABELS = [("heart_rate_bpm", "Heart Rate", "bpm"),
           ("hrv_sdnn_ms", "HRV", "ms"),
           ("breathing_rate_bpm", "Breathing", "/min"),
           ("stress_index", "Stress", ""),
           ("systolic_bp_mmhg", "BP (sys)", "mmHg"),
           ("diastolic_bp_mmhg", "BP (dia)", "mmHg")]


def render_result_card(vitals: Dict[str, Any], width=1280, height=720) -> bytes:
    img = np.zeros((height, width, 3), dtype=np.uint8)
    img[:] = (30, 30, 30)
    cv2.putText(img, "Health Scan Results", (60, 90),
                cv2.FONT_HERSHEY_SIMPLEX, 1.6, (255, 255, 255), 3, cv2.LINE_AA)
    y = 200
    for key, label, unit in _LABELS:
        if key in vitals and vitals[key] is not None:
            val = vitals[key]
            txt = f"{label}: {val:.0f} {unit}".strip()
            cv2.putText(img, txt, (60, y), cv2.FONT_HERSHEY_SIMPLEX, 1.2,
                        (0, 220, 120), 2, cv2.LINE_AA)
            y += 80
    ok, buf = cv2.imencode(".png", img)
    return buf.tobytes() if ok else b""
