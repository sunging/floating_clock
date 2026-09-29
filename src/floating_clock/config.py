"""Config dataclass and persistence (a QSettings INI file, ``config/config.ini``).

Where ``config/`` lives depends on how the program runs; see ``app_dir()``.
"""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Optional
from uuid import uuid4

from PySide6.QtCore import QSettings

from floating_clock import sound
from floating_clock._coerce import clamp_float, clamp_int, clamp_position, to_bool
from floating_clock.alarm import Alarm

# Config lives in a `config` subdir of app_dir(), independent of the working
# directory, so autostart (cwd is usually System32) reads the same file.
CONFIG_DIRNAME = "config"
CONFIG_FILENAME = "config.ini"

# Alarm popup layouts: where the alarm name/content sit relative to the time.
POPUP_LAYOUT_LABEL_TIME = "label_time"  # name/content above, time below
POPUP_LAYOUT_TIME_LABEL = "time_label"  # time above, name/content below
POPUP_LAYOUT_LABEL_ONLY = "label_only"  # name/content only
POPUP_LAYOUTS = (POPUP_LAYOUT_LABEL_TIME, POPUP_LAYOUT_TIME_LABEL, POPUP_LAYOUT_LABEL_ONLY)


def app_dir() -> Path:
    """Return the base directory for the config folder.

    - Packaged as an exe (PyInstaller, ``sys.frozen``): the exe's directory
      (portable mode, config travels with the program).
    - Installed via pip / ``uv tool`` (package under site-packages): a
      user-level directory, so an upgrade/reinstall of the managed environment
      doesn't wipe it.
    - Run directly from source: the project root (parent of ``src``).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    here = Path(__file__).resolve()
    if _is_installed(here):
        return _user_base_dir()
    return here.parents[2]


def _is_installed(path: Path) -> bool:
    """Whether the package lives under site-packages / dist-packages (i.e. installed)."""
    return any(
        parent.name in ("site-packages", "dist-packages")
        for parent in path.parents
    )


def _user_base_dir() -> Path:
    """Return the user-level config base directory (per platform convention)."""
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or str(Path.home())
        return Path(base) / "FloatingClock"
    xdg = os.environ.get("XDG_CONFIG_HOME")
    base = Path(xdg) if xdg else Path.home() / ".config"
    return base / "floating_clock"


def config_dir() -> Path:
    """Return the config folder (``app_dir()/config``), creating it if absent."""
    directory = app_dir() / CONFIG_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def config_path() -> Path:
    """Return the absolute config file path (``app_dir()/config/config.ini``)."""
    return config_dir() / CONFIG_FILENAME


def _settings() -> QSettings:
    """Open the config in INI file format, avoiding the registry."""
    return QSettings(str(config_path()), QSettings.IniFormat)


@dataclass
class Config:
    """All adjustable settings of the floating clock."""

    font_size: int = 48
    opacity: float = 0.75          # 0.1-1.0, overall window opacity
    color: str = "#FFFFFF"         # text color (hex)
    auto_color: bool = False       # auto-adjust text color to background brightness
    auto_color_dark_bg: str = "#F0F0F0"   # (light) text used on a dark background
    auto_color_light_bg: str = "#202020"  # (dark) text used on a light background
    show_seconds: bool = True
    show_date: bool = False
    click_through: bool = True     # click-through by default, doesn't block windows below
    start_on_boot: bool = False    # start on boot
    sound_mode: str = "system"     # silent / system / custom
    sound_system_alias: str = "SystemHand"  # system sound alias
    sound_custom_path: str = ""    # path to a custom sound file (WAV)
    ring_when_screen_off: bool = False  # default: don't ring when the screen is off
    pos_x: Optional[int] = None    # None means center/default position on first launch
    pos_y: Optional[int] = None
    alarm_popup_text_color: str = "#FF3030"
    alarm_popup_background_color: str = "#202020"
    alarm_popup_background_opacity: float = 0.65
    alarm_popup_flash_enabled: bool = True
    alarm_popup_font_scale: float = 1.0
    alarm_popup_layout: str = POPUP_LAYOUT_LABEL_TIME
    alarms: list[Alarm] = field(default_factory=list)

    # ---- Persistence ----
    @classmethod
    def load(cls) -> "Config":
        """Read the config file; missing or malformed values fall back to defaults."""
        s = _settings()
        cfg = cls()
        for name, read in _READERS.items():
            default = getattr(cfg, name)
            setattr(cfg, name, read(s.value(name, default), default))
        cfg.alarms = _load_alarms(s.value("alarms", "[]"))
        return cfg

    def save(self) -> None:
        """Write every setting to the config file (values are normalized on the way out)."""
        s = _settings()
        defaults = Config()
        for name, read in _READERS.items():
            value = read(getattr(self, name), getattr(defaults, name))
            # QSettings can't store None; an empty string reads back as None.
            s.setValue(name, "" if value is None else value)
        s.setValue("alarms", json.dumps([a.to_dict() for a in self.alarms]))
        s.sync()


def _normalize_popup_layout(value) -> str:
    """Coerce the alarm popup layout setting; invalid falls back to label-above-time."""
    value = str(value or POPUP_LAYOUT_LABEL_TIME)
    return value if value in POPUP_LAYOUTS else POPUP_LAYOUT_LABEL_TIME


# ---- Field table ----
# Each scalar Config field maps to a reader ``(raw, default) -> value`` that
# coerces a raw QSettings value (often a string) to the field's type. The INI
# key is the field name. ``alarms`` is stored separately as JSON.
_Reader = Callable[[Any, Any], Any]


def _as_str(raw, _default) -> str:
    return str(raw)


def _as_bool(raw, _default) -> bool:
    return to_bool(raw)


def _int_in(low: int, high: int) -> _Reader:
    return lambda raw, default: clamp_int(raw, low, high, default)


def _float_in(low: float, high: float) -> _Reader:
    return lambda raw, default: clamp_float(raw, low, high, default)


def _as_position(raw, _default) -> Optional[int]:
    return clamp_position(raw)


_READERS: dict[str, _Reader] = {
    "font_size": _int_in(8, 400),
    "opacity": _float_in(0.1, 1.0),
    "color": _as_str,
    "auto_color": _as_bool,
    "auto_color_dark_bg": _as_str,
    "auto_color_light_bg": _as_str,
    "show_seconds": _as_bool,
    "show_date": _as_bool,
    "click_through": _as_bool,
    "start_on_boot": _as_bool,
    "sound_mode": lambda raw, _default: sound.normalize_mode(raw),
    "sound_system_alias": _as_str,
    "sound_custom_path": _as_str,
    "ring_when_screen_off": _as_bool,
    "pos_x": _as_position,
    "pos_y": _as_position,
    "alarm_popup_text_color": _as_str,
    "alarm_popup_background_color": _as_str,
    "alarm_popup_background_opacity": _float_in(0.0, 1.0),
    "alarm_popup_flash_enabled": _as_bool,
    "alarm_popup_font_scale": _float_in(0.5, 3.0),
    "alarm_popup_layout": lambda raw, _default: _normalize_popup_layout(raw),
}


def _load_alarms(raw) -> list[Alarm]:
    """Parse the alarm JSON list, skipping invalid entries and fixing duplicate ids."""
    log = logging.getLogger(__name__)
    try:
        entries = json.loads(raw)
        if not isinstance(entries, list):
            raise ValueError("Alarms must be a list")
    except (ValueError, TypeError):
        log.warning("Invalid alarm list; using an empty list")
        return []
    alarms: list[Alarm] = []
    seen_ids = set()
    for entry in entries:
        try:
            alarm = Alarm.from_dict(entry)
        except (ValueError, TypeError, OverflowError):
            log.warning("Skipping invalid alarm entry")
            continue
        if alarm.id in seen_ids:
            alarm.id = uuid4().hex
        seen_ids.add(alarm.id)
        alarms.append(alarm)
    return alarms
