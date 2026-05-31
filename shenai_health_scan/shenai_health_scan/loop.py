from __future__ import annotations
import threading, time, datetime
from typing import Optional
from .core.types import EngineCmd, Speak, ShowScreen, PublishResults


class MeasurementLoop:
    def __init__(self, camera, engine, orchestrator, robot_io, publisher,
                 submit_fps: int = 30, logger=None):
        self.camera = camera
        self.engine = engine
        self.orch = orchestrator
        self.io = robot_io
        self.pub = publisher
        self.period = 1.0 / submit_fps
        self.log = logger
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        self.camera.start()
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop.is_set():
            self.tick_once(now=time.monotonic())
            time.sleep(self.period)

    def tick_once(self, now: float):
        frame = self.camera.get_latest()
        if frame is not None:
            data, w, h, stride, ts = frame
            try:
                self.engine.submit(data, w, h, stride, ts)
            except Exception as e:
                if self.log: self.log(f"submit_frame failed: {e}")
        poll = self.engine.poll()
        for eff in self.orch.on_tick(poll, now):
            self._dispatch(eff)

    def _dispatch(self, eff):
        if isinstance(eff, EngineCmd):
            if eff.cmd == "reset": self.engine.begin_session()
            elif eff.cmd == "start": self.engine.start()
            elif eff.cmd == "stop": self.engine.stop()
        elif isinstance(eff, Speak):
            if eff.text: self.io.speak(eff.text)
        elif isinstance(eff, ShowScreen):
            self.io.show(eff.view, eff.data)
        elif isinstance(eff, PublishResults):
            self.pub.publish(self._enrich(eff.payload))

    def _enrich(self, payload: dict) -> dict:
        mid = tid = ""
        try:
            mid = self.engine.measurement_id()
            tid = self.engine.trace_id()
        except Exception:
            pass
        payload = dict(payload)
        payload["measurement_id"] = mid
        payload["trace_id"] = tid
        payload["timestamp"] = datetime.datetime.now(datetime.timezone.utc).isoformat()
        return payload

    def stop(self):
        self._stop.set()
        if self._thread: self._thread.join(timeout=2.0)
        self.camera.stop()
