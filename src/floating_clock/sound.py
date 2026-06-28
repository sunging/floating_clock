"""Notification sound playback.

On Windows it uses the built-in ``winsound`` and supports three modes: silent,
system sound, and a custom WAV file. On non-Windows platforms it silently
no-ops (graceful degradation).
"""

from __future__ import annotations

import sys
from pathlib import Path

SOUND_SILENT = "silent"
SOUND_SYSTEM = "system"
SOUND_CUSTOM = "custom"
SOUND_MODES = {SOUND_SILENT, SOUND_SYSTEM, SOUND_CUSTOM}

# Selectable system sounds: winsound SND_ALIAS name -> display name.
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
    """Coerce the sound mode to a supported value; defaults to system sound."""
    value = str(value or SOUND_SYSTEM)
    return value if value in SOUND_MODES else SOUND_SYSTEM


def play(
    mode: str,
    system_alias: str = DEFAULT_SYSTEM_SOUND,
    custom_path: str = "",
    loop: bool = True,
) -> None:
    """Play the sound per config; silent mode or non-Windows just stops/skips."""
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
            # Custom file missing: fall back to the default system sound
            # instead of going completely silent.
            winsound.PlaySound(DEFAULT_SYSTEM_SOUND, winsound.SND_ALIAS | flags)
            return

        alias = str(system_alias or "").strip() or DEFAULT_SYSTEM_SOUND
        winsound.PlaySound(alias, winsound.SND_ALIAS | flags)
    except Exception:
        pass


def stop() -> None:
    """Stop the currently playing sound."""
    if sys.platform != "win32":
        return
    try:
        import winsound

        winsound.PlaySound(None, 0)
    except Exception:
        pass
