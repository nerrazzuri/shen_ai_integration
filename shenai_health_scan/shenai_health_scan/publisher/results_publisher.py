from __future__ import annotations
import json, os, queue, threading, time, uuid
from typing import Optional, Dict, Any

try:
    import requests
except ImportError:  # allow import without requests; fail only on actual POST
    requests = None


class ResultsPublisher:
    def __init__(self, endpoint: Optional[str], auth_header: Optional[str] = None,
                 timeout_sec: float = 5.0, max_retries: int = 3,
                 dead_letter_path: str = "dead_letter"):
        self._endpoint = endpoint
        self._auth = auth_header
        self._timeout = timeout_sec
        self._max_retries = max_retries
        self._dlp = dead_letter_path
        self._q: "queue.Queue" = queue.Queue()
        self._thread: Optional[threading.Thread] = None
        self._stop = threading.Event()

    def start(self):
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def publish(self, payload: Dict[str, Any]):
        self._q.put(payload)

    def flush(self, timeout: float = 5.0):
        end = time.time() + timeout
        while not self._q.empty() and time.time() < end:
            time.sleep(0.02)

    def stop(self):
        self._stop.set()
        self._q.put(None)
        if self._thread:
            self._thread.join(timeout=3.0)

    def _run(self):
        while not self._stop.is_set():
            item = self._q.get()
            if item is None:
                break
            self._deliver(item)

    def _deliver(self, payload: Dict[str, Any]):
        if not self._endpoint or requests is None:
            return self._dead_letter(payload)
        headers = {"Content-Type": "application/json"}
        if self._auth:
            headers["Authorization"] = self._auth
        delay = 0.5
        for attempt in range(self._max_retries):
            try:
                resp = requests.post(self._endpoint, json=payload, headers=headers,
                                     timeout=self._timeout)
                if 200 <= resp.status_code < 300:
                    return
            except Exception:
                pass
            time.sleep(delay); delay *= 2
        self._dead_letter(payload)

    def _dead_letter(self, payload: Dict[str, Any]):
        os.makedirs(self._dlp, exist_ok=True)
        fn = os.path.join(self._dlp, f"result_{int(time.time()*1000)}_{uuid.uuid4().hex[:6]}.json")
        with open(fn, "w") as f:
            json.dump(payload, f)
