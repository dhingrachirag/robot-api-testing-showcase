"""Map HTTP outcomes to a small set of failure categories.

Grouping failures by category (instead of by raw status code or exception
text) makes reports easier to triage: a dashboard showing "12 x TIMEOUT"
tells you far more at a glance than twelve different stack traces.
"""

from __future__ import annotations

import requests

OK = "OK"
AUTH_ERROR = "AUTH_ERROR"
NOT_FOUND = "NOT_FOUND"
VALIDATION_ERROR = "VALIDATION_ERROR"
RATE_LIMITED = "RATE_LIMITED"
CLIENT_ERROR = "CLIENT_ERROR"
SERVER_ERROR = "SERVER_ERROR"
TIMEOUT = "TIMEOUT"
CONNECTION_ERROR = "CONNECTION_ERROR"
SSL_ERROR = "SSL_ERROR"
UNKNOWN = "UNKNOWN"

RETRYABLE = frozenset({RATE_LIMITED, SERVER_ERROR, TIMEOUT, CONNECTION_ERROR})


def classify_status(status_code: int) -> str:
    code = int(status_code)
    if 200 <= code < 400:
        return OK
    if code in (401, 403):
        return AUTH_ERROR
    if code == 404:
        return NOT_FOUND
    if code in (400, 422):
        return VALIDATION_ERROR
    if code == 429:
        return RATE_LIMITED
    if 400 <= code < 500:
        return CLIENT_ERROR
    if 500 <= code < 600:
        return SERVER_ERROR
    return UNKNOWN


def classify_exception(exc: BaseException) -> str:
    # Order matters: SSLError is a subclass of ConnectionError.
    if isinstance(exc, requests.exceptions.SSLError):
        return SSL_ERROR
    if isinstance(exc, requests.exceptions.Timeout):
        return TIMEOUT
    if isinstance(exc, requests.exceptions.ConnectionError):
        return CONNECTION_ERROR
    return UNKNOWN


def is_retryable(category: str) -> bool:
    return category in RETRYABLE
