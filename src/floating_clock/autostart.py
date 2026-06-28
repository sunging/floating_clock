"""Start-on-boot support (Windows Run registry key, current user only, no admin)."""

from __future__ import annotations

import sys
from pathlib import Path

# Value name and key path used in the registry.
APP_NAME = "FloatingClock"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_supported() -> bool:
    return sys.platform == "win32"


def _launch_command() -> str:
    """Build the command line run at boot.

    - When packaged as an exe (PyInstaller, sys.frozen), run the exe directly.
    - When run as a script, use pythonw.exe (no console window) to run
      `-m floating_clock`, pointing at the current interpreter's directory
      (the uv virtual environment).
    """
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    runner = exe.with_name("pythonw.exe")
    if not runner.exists():
        runner = exe
    return f'"{runner}" -m floating_clock'


def is_enabled() -> bool:
    """Query whether start-on-boot is configured."""
    if not is_supported():
        return False
    try:
        import winreg

        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            value, _ = winreg.QueryValueEx(key, APP_NAME)
            return bool(value)
    except FileNotFoundError:
        return False
    except OSError:
        return False


def set_enabled(enabled: bool) -> bool:
    """Enable/disable start-on-boot; return the actual state afterwards."""
    if not is_supported():
        return False
    try:
        import winreg

        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, _RUN_KEY) as key:
            if enabled:
                winreg.SetValueEx(
                    key, APP_NAME, 0, winreg.REG_SZ, _launch_command()
                )
            else:
                try:
                    winreg.DeleteValue(key, APP_NAME)
                except FileNotFoundError:
                    pass
        return enabled
    except OSError:
        # On failure, don't raise; return the real current state.
        return is_enabled()
