"""Unit tests for sound.py: mode normalization and cross-platform silent degradation."""

import sys

import pytest

from floating_clock import sound


@pytest.mark.parametrize(
    "value,expected",
    [
        ("silent", "silent"),
        ("system", "system"),
        ("custom", "custom"),
        ("", "system"),        # empty -> default
        (None, "system"),
        ("nonsense", "system"),  # invalid -> default
    ],
)
def test_normalize_mode(value, expected):
    assert sound.normalize_mode(value) == expected


def test_system_sounds_nonempty_and_contains_default():
    aliases = [alias for alias, _name in sound.SYSTEM_SOUNDS]
    assert sound.DEFAULT_SYSTEM_SOUND in aliases


@pytest.mark.skipif(
    sys.platform == "win32", reason="only verifies silent degradation on non-Windows"
)
def test_play_and_stop_silent_on_non_windows():
    # On non-Windows platforms it should just return without raising.
    sound.play("system", "SystemHand", "", loop=True)
    sound.stop()


def test_play_silent_mode_does_not_raise():
    # Silent mode must not raise on any platform.
    sound.play("silent", "SystemHand", "", loop=True)
    sound.stop()
