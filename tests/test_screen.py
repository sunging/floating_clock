"""screen.py 的单元测试：默认状态与 WM_POWERBROADCAST 解析。"""

import sys

import pytest

from floating_clock.screen import ScreenStateMonitor


def test_default_display_on():
    # 启动时无法查询，默认认为屏幕点亮（宁可响铃也不漏闹钟）。
    assert ScreenStateMonitor().is_display_off() is False


@pytest.mark.skipif(sys.platform != "win32", reason="原生消息解析仅 Windows")
@pytest.mark.parametrize(
    "state,expected_off",
    [
        (0, True),   # 关闭
        (1, False),  # 开启
        (2, False),  # 变暗仍视为点亮
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
    # 过滤器不消费消息，应放行。
    assert handled is False
    assert monitor.is_display_off() is expected_off


@pytest.mark.skipif(sys.platform != "win32", reason="原生消息解析仅 Windows")
def test_unrelated_message_ignored():
    import ctypes

    from floating_clock import screen

    monitor = ScreenStateMonitor()
    msg = screen._MSG()
    msg.message = 0x0001  # 非 WM_POWERBROADCAST
    monitor.nativeEventFilter(b"windows_generic_MSG", ctypes.addressof(msg))
    assert monitor.is_display_off() is False
