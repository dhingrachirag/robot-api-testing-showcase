"""A tiny, dependency-free mock REST API used by the test suites.

It keeps the suites deterministic and runnable offline / in CI. Endpoints:

    GET    /health                 -> {"status": "ok"}
    GET    /items                  -> list of items
    POST   /items                  -> create item (JSON body with "name")
    GET    /items/<id>             -> single item or 404
    DELETE /items/<id>             -> 204 or 404
    POST   /jobs                   -> start an async job, returns {"id", "status": "queued"}
    GET    /jobs/<id>              -> job advances queued -> running -> done on each poll
    GET    /status/<code>          -> responds with that HTTP status code
    GET    /slow?seconds=<n>       -> sleeps n seconds before responding
"""

from __future__ import annotations

import itertools
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

_JOB_STATES = ["queued", "running", "running", "done"]


class _State:
    def __init__(self) -> None:
        self.lock = threading.Lock()
        self.items: dict[int, dict] = {
            1: {"id": 1, "name": "alpha", "tags": ["a", "first"]},
            2: {"id": 2, "name": "beta", "tags": ["b"]},
        }
        self.item_ids = itertools.count(3)
        self.jobs: dict[int, int] = {}  # job id -> number of polls so far
        self.job_ids = itertools.count(1)


class _Handler(BaseHTTPRequestHandler):
    state: _State  # injected by make_server

    # -- helpers ----------------------------------------------------------
    def _send(self, status: int, body=None) -> None:
        payload = b"" if body is None else json.dumps(body).encode()
        self.send_response(status)
        if body is not None:
            self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        try:
            self.wfile.write(payload)
        except (BrokenPipeError, ConnectionResetError):
            pass  # client gave up (e.g. timeout tests) - expected

    def _read_json(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length) if length else b""
        return json.loads(raw) if raw else {}

    def log_message(self, *_args) -> None:  # keep test output quiet
        pass

    # -- routes -----------------------------------------------------------
    def do_GET(self) -> None:  # noqa: N802
        url = urlparse(self.path)
        parts = [p for p in url.path.split("/") if p]
        s = self.state

        if parts == ["health"]:
            return self._send(200, {"status": "ok"})
        if parts == ["items"]:
            with s.lock:
                return self._send(200, list(s.items.values()))
        if len(parts) == 2 and parts[0] == "items" and parts[1].isdigit():
            item = s.items.get(int(parts[1]))
            return self._send(200, item) if item else self._send(404, {"error": "not found"})
        if len(parts) == 2 and parts[0] == "jobs" and parts[1].isdigit():
            job_id = int(parts[1])
            with s.lock:
                if job_id not in s.jobs:
                    return self._send(404, {"error": "not found"})
                polls = s.jobs[job_id]
                s.jobs[job_id] = polls + 1
            status = _JOB_STATES[min(polls, len(_JOB_STATES) - 1)]
            body = {"id": job_id, "status": status}
            if status == "done":
                body["result"] = {"records": 42}
            return self._send(200, body)
        if len(parts) == 2 and parts[0] == "status" and parts[1].isdigit():
            code = int(parts[1])
            return self._send(code, None if code == 204 else {"status": code})
        if parts == ["slow"]:
            seconds = float(parse_qs(url.query).get("seconds", ["1"])[0])
            time.sleep(seconds)
            return self._send(200, {"slept": seconds})
        return self._send(404, {"error": "no route"})

    def do_POST(self) -> None:  # noqa: N802
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        s = self.state
        if parts == ["items"]:
            try:
                data = self._read_json()
            except json.JSONDecodeError:
                return self._send(400, {"error": "invalid json"})
            if not isinstance(data, dict) or not data.get("name"):
                return self._send(422, {"error": "'name' is required"})
            with s.lock:
                new_id = next(s.item_ids)
                item = {"id": new_id, "name": data["name"], "tags": data.get("tags", [])}
                s.items[new_id] = item
            return self._send(201, item)
        if parts == ["jobs"]:
            with s.lock:
                job_id = next(s.job_ids)
                s.jobs[job_id] = 0
            return self._send(202, {"id": job_id, "status": "queued"})
        return self._send(404, {"error": "no route"})

    def do_DELETE(self) -> None:  # noqa: N802
        parts = [p for p in urlparse(self.path).path.split("/") if p]
        if len(parts) == 2 and parts[0] == "items" and parts[1].isdigit():
            with self.state.lock:
                removed = self.state.items.pop(int(parts[1]), None)
            return self._send(204) if removed else self._send(404, {"error": "not found"})
        return self._send(404, {"error": "no route"})


def make_server(host: str = "127.0.0.1", port: int = 0) -> ThreadingHTTPServer:
    """Create a server with fresh state. Port 0 picks a free port."""
    handler = type("Handler", (_Handler,), {"state": _State()})
    return ThreadingHTTPServer((host, port), handler)


if __name__ == "__main__":
    server = make_server(port=8000)
    print("Mock API listening on http://127.0.0.1:8000")
    server.serve_forever()
