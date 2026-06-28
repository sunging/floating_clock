"""提示音播放。

Windows 上用内置 ``winsound`` 播放，支持三种模式：无声、系统提示音、
自定义 WAV 文件。非 Windows 平台静默跳过（功能优雅降级）。
"""

from __future__ import annotations

import sys
from pathlib import Path

SOUND_SILENT = "silent"
SOUND_SYSTEM = "system"
SOUND_CUSTOM = "custom"
SOUND_MODES = {SOUND_SILENT, SOUND_SYSTEM, SOUND_CUSTOM}

# 可选的系统提示音：winsound SND_ALIAS 别名 -> 显示名。
SYSTEM_SOUNDS: list[tuple[str, str]] = [
    ("SystemHand", "错误 (Critical Stop)"),
    ("SystemAsterisk", "星号 (Asterisk)"),
    ("SystemExclamation", "感叹 (Exclamation)"),
    ("SystemQuestion", "问题 (Question)"),
    ("SystemDefault", "默认提示音"),
    ("SystemStart", "Windows 启动"),
    ("SystemExit", "Windows 退出"),
]
DEFAULT_SYSTEM_SOUND = "SystemHand"


def normalize_mode(value) -> str:
    """把提示音模式规整到支持的取值，默认系统提示音。"""
    value = str(value or SOUND_SYSTEM)
    return value if value in SOUND_MODES else SOUND_SYSTEM


def play(
    mode: str,
    system_alias: str = DEFAULT_SYSTEM_SOUND,
    custom_path: str = "",
    loop: bool = True,
) -> None:
    """按配置播放提示音；无声模式或非 Windows 平台直接停声/跳过。"""
    if sys.platform != "win32":
        return
    mode = normalize_mode(mode)
    if mode == SOUND_SILENT:
        stop()
        return
    try:
        import winsound

        flags = winsound.SND_ASYNC
        if loop:
            flags |= winsound.SND_LOOP

        if mode == SOUND_CUSTOM:
            path = str(custom_path or "").strip()
            if path and Path(path).is_file():
                winsound.PlaySound(path, winsound.SND_FILENAME | flags)
                return
            # 自定义文件缺失时回退到默认系统提示音，避免完全无声。
            winsound.PlaySound(DEFAULT_SYSTEM_SOUND, winsound.SND_ALIAS | flags)
            return

        alias = str(system_alias or "").strip() or DEFAULT_SYSTEM_SOUND
        winsound.PlaySound(alias, winsound.SND_ALIAS | flags)
    except Exception:
        pass


def stop() -> None:
    """停止当前正在播放的提示音。"""
    if sys.platform != "win32":
        return
    try:
        import winsound

        winsound.PlaySound(None, 0)
    except Exception:
        pass
