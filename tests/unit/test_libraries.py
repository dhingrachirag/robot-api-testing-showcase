import pytest
import requests

from libraries import error_classifier as ec
from libraries.json_path import get_value
from libraries.polling import PollTimeout, poll_until


# ---------------------------------------------------------------- classifier
@pytest.mark.parametrize(
    "status, category",
    [
        (200, ec.OK), (204, ec.OK), (302, ec.OK),
        (401, ec.AUTH_ERROR), (403, ec.AUTH_ERROR),
        (404, ec.NOT_FOUND), (400, ec.VALIDATION_ERROR), (422, ec.VALIDATION_ERROR),
        (429, ec.RATE_LIMITED), (409, ec.CLIENT_ERROR),
        (500, ec.SERVER_ERROR), (503, ec.SERVER_ERROR), (999, ec.UNKNOWN),
    ],
)
def test_classify_status(status, category):
    assert ec.classify_status(status) == category


@pytest.mark.parametrize(
    "exc, category",
    [
        (requests.exceptions.SSLError(), ec.SSL_ERROR),
        (requests.exceptions.ReadTimeout(), ec.TIMEOUT),
        (requests.exceptions.ConnectTimeout(), ec.TIMEOUT),
        (requests.exceptions.ConnectionError(), ec.CONNECTION_ERROR),
        (ValueError(), ec.UNKNOWN),
    ],
)
def test_classify_exception(exc, category):
    assert ec.classify_exception(exc) == category


def test_only_transient_categories_are_retryable():
    assert ec.is_retryable(ec.SERVER_ERROR)
    assert not ec.is_retryable(ec.NOT_FOUND)


# ----------------------------------------------------------------- json path
DATA = {"result": {"items": [{"id": 7, "tags": ["x", "y"]}], "count": 1}}


@pytest.mark.parametrize(
    "path, expected",
    [
        ("result.count", 1),
        ("result.items[0].id", 7),
        ("result.items[0].tags[-1]", "y"),
        ("", DATA),
    ],
)
def test_get_value(path, expected):
    assert get_value(DATA, path) == expected


def test_get_value_on_top_level_list():
    assert get_value([{"a": 1}], "[0].a") == 1


def test_missing_path_raises_or_returns_default():
    with pytest.raises(KeyError):
        get_value(DATA, "result.items[5].id")
    assert get_value(DATA, "result.nope", default="n/a") == "n/a"


def test_invalid_path_syntax():
    with pytest.raises(ValueError):
        get_value(DATA, "result..count]x")


# ------------------------------------------------------------------- polling
class FakeClock:
    def __init__(self):
        self.now = 0.0
        self.sleeps = []

    def time(self):
        return self.now

    def sleep(self, seconds):
        self.sleeps.append(seconds)
        self.now += seconds


def test_poll_succeeds_with_exponential_backoff():
    clock = FakeClock()
    values = iter(["queued", "running", "running", "done"])
    result = poll_until(
        lambda: next(values), lambda v: v == "done",
        timeout=30, interval=0.5, backoff=2, max_interval=1.5,
        sleep=clock.sleep, clock=clock.time,
    )
    assert result.value == "done"
    assert result.attempts == 4
    assert clock.sleeps == [0.5, 1.0, 1.5]  # doubled, then capped


def test_poll_times_out():
    clock = FakeClock()
    with pytest.raises(PollTimeout):
        poll_until(lambda: "running", lambda v: v == "done",
                   timeout=3, interval=1, sleep=clock.sleep, clock=clock.time)
    assert clock.now <= 3


def test_poll_fails_fast_on_terminal_state():
    clock = FakeClock()
    values = iter(["running", "failed", "done"])
    with pytest.raises(AssertionError, match="Terminal state"):
        poll_until(lambda: next(values), lambda v: v == "done",
                   fail_fast=lambda v: v == "failed",
                   sleep=clock.sleep, clock=clock.time)


def test_poll_rejects_bad_arguments():
    with pytest.raises(ValueError):
        poll_until(lambda: 1, bool, timeout=0)
