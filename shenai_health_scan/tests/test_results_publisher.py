import json, threading, http.server, tempfile, os
from shenai_health_scan.publisher.results_publisher import ResultsPublisher

class _Handler(http.server.BaseHTTPRequestHandler):
    received = []
    def do_POST(self):
        n = int(self.headers.get("Content-Length", 0))
        _Handler.received.append(json.loads(self.rfile.read(n)))
        self.send_response(200); self.end_headers()
    def log_message(self, *a): pass

def _server():
    srv = http.server.HTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv

def test_posts_payload():
    _Handler.received.clear()
    srv = _server(); port = srv.server_address[1]
    pub = ResultsPublisher(endpoint=f"http://127.0.0.1:{port}/r", auth_header=None)
    pub.start(); pub.publish({"hello": "world"}); pub.flush(timeout=3.0); pub.stop()
    srv.shutdown()
    assert _Handler.received == [{"hello": "world"}]

def test_dead_letter_on_failure():
    d = tempfile.mkdtemp()
    pub = ResultsPublisher(endpoint="http://127.0.0.1:1/none", auth_header=None,
                           max_retries=1, timeout_sec=0.2, dead_letter_path=d)
    pub.start(); pub.publish({"x": 1}); pub.flush(timeout=5.0); pub.stop()
    files = os.listdir(d)
    assert len(files) == 1 and json.load(open(os.path.join(d, files[0])))["x"] == 1
