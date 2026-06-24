"""开机自启动支持（Windows 注册表 Run 键，仅当前用户，无需管理员权限）。"""

from __future__ import annotations

import sys
from pathlib import Path

# 注册表中使用的值名称与路径。
APP_NAME = "FloatingClock"
_RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"


def is_supported() -> bool:
    return sys.platform == "win32"


def _launch_command() -> str:
    """构造开机启动时执行的命令行。

    - 打包成 exe（PyInstaller，sys.frozen）时直接运行该 exe。
    - 作为脚本运行时用 pythonw.exe（无控制台窗口）执行 `-m floating_clock`，
      指向当前解释器（uv 虚拟环境）所在目录。
    """
    exe = Path(sys.executable)
    if getattr(sys, "frozen", False):
        return f'"{exe}"'
    runner = exe.with_name("pythonw.exe")
    if not runner.exists():
        runner = exe
    return f'"{runner}" -m floating_clock'


def is_enabled() -> bool:
    """查询是否已配置开机启动。"""
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
    """启用 / 关闭开机启动；返回操作后的实际状态。"""
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
        # 失败时不抛异常，返回当前真实状态。
        return is_enabled()
