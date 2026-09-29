"""Unit tests for _coerce.py (lenient value coercion)."""

import pytest

from floating_clock._coerce import clamp_float, clamp_int, clamp_position, to_bool


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        ("true", True),
        ("TRUE", True),
        (" 1 ", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("", False),
        (1, True),
        (0, False),
        (None, False),
    ],
)
def test_to_bool(value, expected):
    assert to_bool(value) is expected


def test_clamp_float():
    assert clamp_float(0.5, 0.0, 1.0, 0.75) == 0.5
    assert clamp_float("0.25", 0.0, 1.0, 0.75) == 0.25
    assert clamp_float(1.5, 0.0, 1.0, 0.75) == 1.0   # clamp to upper bound
    assert clamp_float(-1, 0.0, 1.0, 0.75) == 0.0    # clamp to lower bound
    assert clamp_float("bad", 0.0, 1.0, 0.75) == 0.75  # invalid -> default
    assert clamp_float(None, 0.0, 1.0, 0.75) == 0.75
    assert clamp_float("nan", 0.0, 1.0, 0.75) == 0.75
    assert clamp_float("inf", 0.0, 1.0, 0.75) == 0.75


def test_clamp_int():
    assert clamp_int("12", 8, 400, 48) == 12
    assert clamp_int(1, 8, 400, 48) == 8
    assert clamp_int(1000, 8, 400, 48) == 400
    assert clamp_int("bad", 8, 400, 48) == 48
    assert clamp_int(None, 8, 400, 48) == 48
    assert clamp_int(float("inf"), 8, 400, 48) == 48


@pytest.mark.parametrize(
    "value,expected",
    [
        (100, 100),
        ("-1920", -1920),
        ("", None),
        (None, None),
        ("bad", None),
        ("inf", None),
        (10**7, None),
    ],
)
def test_clamp_position(value, expected):
    assert clamp_position(value) == expected
