"""显示器电源状态监听（Windows）。

通过 ``RegisterPowerSettingNotification`` 订阅 ``GUID_CONSOLE_DISPLAY_STATE``，
作为 Qt 原生事件过滤器解析 ``WM_POWERBROADCAST`` 消息，维护"屏幕是否点亮"。
用于"屏幕关闭时不响铃"的判断。非 Windows 平台为无操作，始终认为屏幕点亮。
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter

_WM_POWERBROADCAST = 0x0218
_PBT_POWERSETTINGCHANGE = 0x8013
_DEVICE_NOTIFY_WINDOW_HANDLE = 0x0

# 显示状态值：0=关闭，1=开启，2=变暗。
_DISPLAY_OFF = 0

if sys.platform == "win32":
    import ctypes
    from ctypes import wintypes

    class _GUID(ctypes.Structure):
        _fields_ = [
            ("Data1", ctypes.c_ulong),
            ("Data2", ctypes.c_ushort),
            ("Data3", ctypes.c_ushort),
            ("Data4", ctypes.c_ubyte * 8),
        ]

    class _MSG(ctypes.Structure):
        _fields_ = [
            ("hwnd", wintypes.HWND),
            ("message", wintypes.UINT),
            ("wParam", wintypes.WPARAM),
            ("lParam", wintypes.LPARAM),
            ("time", wintypes.DWORD),
            ("pt_x", wintypes.LONG),
            ("pt_y", wintypes.LONG),
        ]

    class _POWERBROADCAST_SETTING(ctypes.Structure):
        _fields_ = [
            ("PowerSetting", _GUID),
            ("DataLength", wintypes.DWORD),
            ("Data", ctypes.c_ubyte * 4),
        ]

    # GUID_CONSOLE_DISPLAY_STATE {6FE69556-704A-47A0-8F24-C28D936FDA47}
    _CONSOLE_DISPLAY_STATE = _GUID(
        0x6FE69556,
        0x704A,
        0x47A0,
        (ctypes.c_ubyte * 8)(0x8F, 0x24, 0xC2, 0x8D, 0x93, 0x6F, 0xDA, 0x47),
    )


class ScreenStateMonitor(QAbstractNativeEventFilter):
    """跟踪显示器电源状态；安装为应用级原生事件过滤器后调用 ``start``。"""

    def __init__(self) -> None:
        super().__init__()
        # 启动时无法直接查询，默认认为屏幕点亮（宁可响铃也不漏闹钟）。
        self._display_on = True
        self._handle = None

    def is_display_off(self) -> bool:
        return not self._display_on

    def start(self, hwnd: int) -> bool:
        """为指定窗口句柄订阅显示状态通知；成功返回 True。"""
        if sys.platform != "win32" or not hwnd:
            return False
        try:
            user32 = ctypes.windll.user32
            user32.RegisterPowerSettingNotification.restype = wintypes.HANDLE
            user32.RegisterPowerSettingNotification.argtypes = [
                wintypes.HANDLE,
                ctypes.c_void_p,
                wintypes.DWORD,
            ]
            self._handle = user32.RegisterPowerSettingNotification(
                wintypes.HANDLE(int(hwnd)),
                ctypes.byref(_CONSOLE_DISPLAY_STATE),
                _DEVICE_NOTIFY_WINDOW_HANDLE,
            )
            return bool(self._handle)
        except Exception:
            return False

    def nativeEventFilter(self, eventType, message):  # noqa: N802 (Qt 命名)
        if sys.platform != "win32":
            return False, 0
        try:
            kind = bytes(eventType) if eventType is not None else b""
            if kind != b"windows_generic_MSG":
                return False, 0
            msg = _MSG.from_address(int(message))
            if (
                msg.message == _WM_POWERBROADCAST
                and msg.wParam == _PBT_POWERSETTINGCHANGE
                and msg.lParam
            ):
                setting = _POWERBROADCAST_SETTING.from_address(int(msg.lParam))
                if bytes(setting.PowerSetting) == bytes(_CONSOLE_DISPLAY_STATE):
                    self._display_on = setting.Data[0] != _DISPLAY_OFF
        except Exception:
            pass
        return False, 0
