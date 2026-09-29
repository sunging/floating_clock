"""Lenient value coercion shared by config and alarm loading.

Persisted data (INI values, alarm JSON) may be hand-edited or written by an
older version, so every reader here falls back instead of raising.
"""

from __future__ import annotations

import math
from typing import Optional

# Coordinates outside this range are treated as corrupt rather than passed to Qt.
_POSITION_LIMIT = 1_000_000


def to_bool(value) -> bool:
    """Normalize a bool that may have been stored as a string ("true", "1", ...)."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def clamp_float(value, low: float, high: float, default: float) -> float:
    """Read a float and clamp it to [low, high]; malformed or non-finite -> default."""
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return default
    if not math.isfinite(number):
        return default
    return max(low, min(high, number))


def clamp_int(value, low: int, high: int, default: int) -> int:
    """Read an int and clamp it to [low, high]; malformed -> default."""
    try:
        return max(low, min(high, int(value)))
    except (TypeError, ValueError, OverflowError):
        return default


def clamp_position(value) -> Optional[int]:
    """Read a screen coordinate; missing, malformed, or implausible -> None."""
    try:
        position = int(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return position if -_POSITION_LIMIT <= position <= _POSITION_LIMIT else None
