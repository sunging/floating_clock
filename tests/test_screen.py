"""Unit tests for screen.py: default state and WM_POWERBROADCAST parsing."""

import sys

import pytest

from floating_clock.screen import ScreenStateMonitor


def test_default_display_on():
    # The state can't be queried at startup; assume the screen is on
    # (better to ring than to miss an alarm).
    assert ScreenStateMonitor().is_display_off() is False


@pytest.mark.skipif(sys.platform != "win32", reason="native message parsing is Windows-only")
@pytest.mark.parametrize(
    "state,expected_off",
    [
        (0, True),   # off
        (1, False),  # on
        (2, False),  # dimmed still counts as on
    ],
)
def test_power_broadcast_updates_state(state, expected_off):
    import ctypes

    from floating_clock import screen

    setting = screen._POWERBROADCAST_SETTING()
    setting.PowerSetting = screen._CONSOLE_DISPLAY_STATE
    setting.DataLength = 4
    setting.Data[0] = state

    msg = screen._MSG()
    msg.message = 0x0218  # WM_POWERBROADCAST
    msg.wParam = 0x8013   # PBT_POWERSETTINGCHANGE
    msg.lParam = ctypes.addressof(setting)

    monitor = ScreenStateMonitor()
    handled, _ = monitor.nativeEventFilter(
        b"windows_generic_MSG", ctypes.addressof(msg)
    )
    # The filter doesn't consume the message; it should pass it through.
    assert handled is False
    assert monitor.is_display_off() is expected_off


@pytest.mark.skipif(sys.platform != "win32", reason="native message parsing is Windows-only")
def test_unrelated_message_ignored():
    import ctypes

    from floating_clock import screen

    monitor = ScreenStateMonitor()
    msg = screen._MSG()
    msg.message = 0x0001  # not WM_POWERBROADCAST
    monitor.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))
    assert monitor.is_display_off() is False
