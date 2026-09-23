"""Robot Framework keyword library for REST API testing.

Highlights:
* One shared ``requests.Session`` per suite run (connection pooling / keep-alive).
* Optional mutual-TLS client certificates, configured via environment variables.
* Every response is classified (OK, TIMEOUT, SERVER_ERROR, ...) for faster triage.
* Automatic retries with backoff for retryable categories only.
* Async-job polling with exponential backoff and fail-fast on terminal states.
"""

from __future__ import annotations

import os
import threading
import time
from typing import Any

import requests
from requests.adapters import HTTPAdapter
from robot.api import logger
from robot.api.deco import keyword, library

from libraries import error_classifier as ec
from libraries.json_path import get_value
from libraries.polling import poll_until
from mock_server.app import make_server


@library(scope="GLOBAL", auto_keywords=False)
class ApiLibrary:
    def __init__(self, base_url: str | None = None, timeout: float = 10.0) -> None:
        self.base_url = (base_url or os.getenv("API_BASE_URL", "")).rstrip("/")
        self.timeout = float(os.getenv("API_TIMEOUT", timeout))
        self._session: requests.Session | None = None
        self.sessions_created = 0
        self.requests_sent = 0
        self._server = None

    # ------------------------------------------------------------------ setup
    @keyword
    def start_mock_server(self) -> str:
        """Start the bundled mock API on a free port and point the client at it.

        Skipped when ``API_BASE_URL`` is set, so the same suites can run against
        a real deployment.
        """
        self.sessions_created = self.requests_sent = 0  # stats are per suite
        if os.getenv("API_BASE_URL"):
            logger.info(f"API_BASE_URL set; using {self.base_url} instead of the mock server")
            return self.base_url
        self._server = make_server()
        threading.Thread(target=self._server.serve_forever, daemon=True).start()
        host, port = self._server.server_address[:2]
        self.base_url = f"http://{host}:{port}"
        logger.info(f"Mock server started at {self.base_url}")
        return self.base_url

    @keyword
    def stop_mock_server(self) -> None:
        if self._server:
            self._server.shutdown()
            self._server.server_close()
            self._server = None
        self.close_session()

    @keyword
    def close_session(self) -> None:
        if self._session:
            self._session.close()
            self._session = None

    def _get_session(self) -> requests.Session:
        if self._session is None:
            session = requests.Session()
            session.headers.update({"Accept": "application/json", "User-Agent": "robot-api-showcase/1.0"})
            adapter = HTTPAdapter(pool_connections=4, pool_maxsize=10)
            session.mount("http://", adapter)
            session.mount("https://", adapter)
            # Mutual TLS: supply PEM cert/key paths via env vars, never commit them.
            cert, key = os.getenv("CLIENT_CERT"), os.getenv("CLIENT_KEY")
            if cert:
                session.cert = (cert, key) if key else cert
            if os.getenv("CA_BUNDLE"):
                session.verify = os.environ["CA_BUNDLE"]
            if token := os.getenv("API_TOKEN"):
                session.headers["Authorization"] = f"Bearer {token}"
            self._session = session
            self.sessions_created += 1
        return self._session

    # --------------------------------------------------------------- requests
    @keyword
    def send_request(
        self,
        method: str,
        path: str,
        json: Any = None,
        params: dict | None = None,
        expected_status: int | None = None,
        retries: int = 0,
        timeout: float | None = None,
    ) -> dict:
        """Send a request and return a dict with ``status``, ``body``, ``category``,
        ``elapsed_ms`` and ``attempts``.

        Retries (with backoff) only when the failure category is retryable,
        so a 404 or 422 fails immediately instead of wasting time.
        """
        if not self.base_url:
            raise RuntimeError("No base URL: set API_BASE_URL or call 'Start Mock Server'")
        url = f"{self.base_url}/{path.lstrip('/')}"
        retries = int(retries)
        timeout = float(timeout) if timeout is not None else self.timeout
        attempt, delay = 0, 0.2
        while True:
            attempt += 1
            result = self._send_once(method.upper(), url, json, params, timeout)
            result["attempts"] = attempt
            if not ec.is_retryable(result["category"]) or attempt > retries:
                break
            logger.info(f"{result['category']} on attempt {attempt}; retrying in {delay:.1f}s")
            time.sleep(delay)
            delay = min(delay * 2, 2.0)

        logger.info(
            f"{method.upper()} {url} -> {result['status']} [{result['category']}] "
            f"in {result['elapsed_ms']} ms (attempts: {attempt})"
        )
        if expected_status is not None and result["status"] != int(expected_status):
            raise AssertionError(
                f"Expected status {expected_status} but got {result['status']} "
                f"[{result['category']}] from {method.upper()} {path}. Body: {result['body']!r}"
            )
        return result

    def _send_once(self, method, url, json, params, timeout) -> dict:
        started = time.perf_counter()
        self.requests_sent += 1
        try:
            resp = self._get_session().request(method, url, json=json, params=params, timeout=timeout)
        except requests.exceptions.RequestException as exc:
            return {
                "status": None,
                "body": str(exc),
                "category": ec.classify_exception(exc),
                "elapsed_ms": round((time.perf_counter() - started) * 1000),
            }
        try:
            body = resp.json() if resp.content else None
        except ValueError:
            body = resp.text
        return {
            "status": resp.status_code,
            "body": body,
            "category": ec.classify_status(resp.status_code),
            "elapsed_ms": round((time.perf_counter() - started) * 1000),
        }

    # ---------------------------------------------------------------- helpers
    @keyword
    def get_json_value(self, data: Any, path: str, default: Any = None) -> Any:
        """Read a nested value, e.g. ``result.items[0].id``. Fails if missing and no default."""
        return get_value(data, path) if default is None else get_value(data, path, default)

    @keyword
    def wait_until_json_field_equals(
        self,
        path: str,
        field: str,
        expected: str,
        timeout: float = 30,
        interval: float = 0.2,
        fail_values: str = "",
    ) -> dict:
        """Poll ``GET path`` until ``field`` equals ``expected``.

        ``fail_values`` is a comma-separated list of terminal states (e.g.
        ``failed,cancelled``) that stop polling immediately.
        """
        terminal = {v.strip() for v in fail_values.split(",") if v.strip()}

        def fetch():
            return self.send_request("GET", path, expected_status=200)["body"]

        def field_value(body):
            return str(get_value(body, field, default=None))

        result = poll_until(
            fetch,
            condition=lambda b: field_value(b) == str(expected),
            fail_fast=(lambda b: field_value(b) in terminal) if terminal else None,
            timeout=float(timeout),
            interval=float(interval),
        )
        seen = [field_value(b) for b in result.history]
        logger.info(f"Reached {field}={expected} after {result.attempts} polls ({result.elapsed:.2f}s): {seen}")
        return result.value

    @keyword
    def session_should_have_been_reused(self) -> None:
        """Assert all requests in the current suite went through a single session."""
        if self.sessions_created != 1:
            raise AssertionError(f"Expected 1 session, but {self.sessions_created} were created")
        logger.info(f"{self.requests_sent} requests shared 1 session")
