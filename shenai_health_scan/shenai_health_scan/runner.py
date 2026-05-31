from __future__ import annotations
from typing import List, Optional
from .core.config import ScanConfig
from .core.orchestrator import ScanOrchestrator
from .publisher.results_publisher import ResultsPublisher
from .loop import MeasurementLoop


class ScanApp:
    def __init__(self, config: ScanConfig, camera, engine, robot_io,
                 triggers: List, logger=None):
        self.config = config
        self.orch = ScanOrchestrator(
            acquire_face_timeout=config.acquire_face_timeout,
            max_measure_seconds=config.max_measure_seconds,
            min_signal_quality=config.min_signal_quality)
        self.publisher = ResultsPublisher(
            endpoint=config.publisher.endpoint,
            auth_header=config.publisher.auth_header,
            timeout_sec=config.publisher.timeout_sec,
            max_retries=config.publisher.max_retries,
            dead_letter_path=config.publisher.dead_letter_path)
        self.loop = MeasurementLoop(camera, engine, self.orch, robot_io,
                                    self.publisher, submit_fps=config.submit_fps,
                                    logger=logger)
        self.triggers = triggers

    def request_scan(self):
        self.orch.request_scan()

    def start(self):
        self.publisher.start()
        self.loop.start()
        for t in self.triggers:
            t.start(self.request_scan)

    def stop(self):
        for t in self.triggers:
            t.stop()
        self.loop.stop()
        self.publisher.flush(timeout=3.0)
        self.publisher.stop()
