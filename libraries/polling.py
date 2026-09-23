"""Generic poll-until-condition helper with exponential backoff.

Many APIs are asynchronous: you submit a job, then check back until it
finishes. Polling with a capped exponential backoff keeps early checks
fast while avoiding hammering the server on long-running jobs.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any, Callable


class PollTimeout(AssertionError):
    """Raised when the condition is not met within the timeout."""


@dataclass
class PollResult:
    value: Any
    attempts: int
    elapsed: float
    history: list = field(default_factory=list)


def poll_until(
    fetch: Callable[[], Any],
    condition: Callable[[Any], bool],
    timeout: float = 30.0,
    interval: float = 0.5,
    backoff: float = 2.0,
    max_interval: float = 5.0,
    fail_fast: Callable[[Any], bool] | None = None,
    sleep: Callable[[float], None] = time.sleep,
    clock: Callable[[], float] = time.monotonic,
) -> PollResult:
    """Call ``fetch`` until ``condition(value)`` is true.

    ``fail_fast`` lets callers stop immediately on terminal failure states
    (e.g. ``status == "failed"``) instead of waiting for the full timeout.
    ``sleep`` and ``clock`` are injectable so the logic is unit-testable
    without real waiting.
    """
    if timeout <= 0 or interval <= 0 or backoff < 1:
        raise ValueError("timeout and interval must be > 0 and backoff >= 1")

    start = clock()
    delay = interval
    history: list = []
    attempts = 0
    while True:
        attempts += 1
        value = fetch()
        history.append(value)
        elapsed = clock() - start
        if condition(value):
            return PollResult(value, attempts, elapsed, history)
        if fail_fast is not None and fail_fast(value):
            raise AssertionError(f"Terminal state reached after {attempts} attempt(s): {value!r}")
        remaining = timeout - elapsed
        if remaining <= 0:
            raise PollTimeout(
                f"Condition not met after {attempts} attempt(s) in {elapsed:.1f}s; last value: {value!r}"
            )
        sleep(min(delay, remaining))
        delay = min(delay * backoff, max_interval)
