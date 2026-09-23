"""Minimal path-based lookup for nested JSON, e.g. ``result.items[0].id``.

Kept dependency-free on purpose; for full JSONPath use a library such as
``jsonpath-ng``.
"""

from __future__ import annotations

import re
from typing import Any

_TOKEN = re.compile(r"([^.\[\]]+)|\[(-?\d+)\]")
_MISSING = object()


def _tokens(path: str) -> list:
    if not path:
        return []
    tokens, pos = [], 0
    for match in _TOKEN.finditer(path):
        gap = path[pos:match.start()]
        if gap not in ("", "."):
            raise ValueError(f"Invalid path syntax near {gap!r} in {path!r}")
        key, index = match.groups()
        tokens.append(int(index) if index is not None else key)
        pos = match.end()
    if path[pos:] not in ("",):
        raise ValueError(f"Invalid path syntax at end of {path!r}")
    return tokens


def get_value(data: Any, path: str, default: Any = _MISSING) -> Any:
    """Return the value at ``path`` or ``default``; raise KeyError if no default."""
    current = data
    for token in _tokens(path):
        try:
            if isinstance(token, int):
                if not isinstance(current, list):
                    raise TypeError
                current = current[token]
            else:
                if not isinstance(current, dict):
                    raise TypeError
                current = current[token]
        except (KeyError, IndexError, TypeError):
            if default is _MISSING:
                raise KeyError(f"Path {path!r} not found (failed at {token!r})") from None
            return default
    return current
