"""Monitor power state detection (Windows).

Subscribes to ``GUID_CONSOLE_DISPLAY_STATE`` via
``RegisterPowerSettingNotification`` and, as a Qt native event filter, parses
``WM_POWERBROADCAST`` messages to track whether the screen is on. Used for the
"don't ring when the screen is off" behavior. On non-Windows platforms it is a
no-op and always reports the screen as on.
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QAbstractNativeEventFilter

_WM_POWERBROADCAST = 0x0218
_PBT_POWERSETTINGCHANGE = 0x8013
_DEVICE_NOTIFY_WINDOW_HANDLE = 0x0

# Display state values: 0=off, 1=on, 2=dimmed.
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
    """Tracks monitor power state; call ``start`` after installing as an app-level filter."""

    def __init__(self) -> None:
        super().__init__()
        # The state can't be queried at startup; assume the screen is on
        # (better to ring than to miss an alarm).
        self._display_on = True
        self._handle = None

    def is_display_off(self) -> bool:
        return not self._display_on

    def start(self, hwnd: int) -> bool:
        """Subscribe to display-state notifications for the given window handle; True on success."""
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

    def nativeEventFilter(self, eventType, message):  # noqa: N802 (Qt naming)
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
