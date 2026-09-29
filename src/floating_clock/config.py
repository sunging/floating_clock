"""Config dataclass and persistence (QSettings INI file under the program's config dir)."""

from __future__ import annotations

import json
import logging
import os
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
from uuid import uuid4

from PySide6.QtCore import QSettings

from floating_clock import sound
from floating_clock._coerce import clamp_float, clamp_int, clamp_position, to_bool
from floating_clock.alarm import Alarm

# Config lives in a `config` subdir under the program directory, independent of
# the working directory, so autostart (cwd is usually System32) reads the same file.
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
    """Return the config folder (config/ under the program dir), creating it if absent."""
    directory = app_dir() / CONFIG_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def config_path() -> Path:
    """Return the absolute config file path (config/config.ini under the program dir)."""
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
        s = _settings()
        cfg = cls()
        cfg.font_size = clamp_int(s.value("font_size", cfg.font_size), 8, 400, cfg.font_size)
        cfg.opacity = clamp_float(s.value("opacity", cfg.opacity), 0.1, 1.0, cfg.opacity)
        cfg.color = str(s.value("color", cfg.color))
        cfg.auto_color = to_bool(s.value("auto_color", cfg.auto_color))
        cfg.auto_color_dark_bg = str(
            s.value("auto_color_dark_bg", cfg.auto_color_dark_bg)
        )
        cfg.auto_color_light_bg = str(
            s.value("auto_color_light_bg", cfg.auto_color_light_bg)
        )
        cfg.show_seconds = to_bool(s.value("show_seconds", cfg.show_seconds))
        cfg.show_date = to_bool(s.value("show_date", cfg.show_date))
        cfg.click_through = to_bool(s.value("click_through", cfg.click_through))
        cfg.start_on_boot = to_bool(s.value("start_on_boot", cfg.start_on_boot))
        cfg.sound_mode = sound.normalize_mode(
            s.value("sound_mode", cfg.sound_mode)
        )
        cfg.sound_system_alias = str(
            s.value("sound_system_alias", cfg.sound_system_alias)
        )
        cfg.sound_custom_path = str(
            s.value("sound_custom_path", cfg.sound_custom_path)
        )
        cfg.ring_when_screen_off = to_bool(
            s.value("ring_when_screen_off", cfg.ring_when_screen_off)
        )
        cfg.alarm_popup_text_color = str(
            s.value("alarm_popup_text_color", cfg.alarm_popup_text_color)
        )
        cfg.alarm_popup_background_color = str(
            s.value(
                "alarm_popup_background_color",
                cfg.alarm_popup_background_color,
            )
        )
        cfg.alarm_popup_background_opacity = clamp_float(
            s.value(
                "alarm_popup_background_opacity",
                cfg.alarm_popup_background_opacity,
            ),
            0.0,
            1.0,
            cfg.alarm_popup_background_opacity,
        )
        cfg.alarm_popup_flash_enabled = to_bool(
            s.value(
                "alarm_popup_flash_enabled",
                cfg.alarm_popup_flash_enabled,
            )
        )
        cfg.alarm_popup_font_scale = clamp_float(
            s.value("alarm_popup_font_scale", cfg.alarm_popup_font_scale),
            0.5,
            3.0,
            cfg.alarm_popup_font_scale,
        )
        cfg.alarm_popup_layout = _normalize_popup_layout(
            s.value("alarm_popup_layout", cfg.alarm_popup_layout)
        )

        px = s.value("pos_x", None)
        py = s.value("pos_y", None)
        cfg.pos_x = clamp_position(px)
        cfg.pos_y = clamp_position(py)

        raw = s.value("alarms", "[]")
        try:
            entries = json.loads(raw)
            if not isinstance(entries, list):
                raise ValueError("Alarms must be a list")
        except (ValueError, TypeError):
            logging.getLogger(__name__).warning("Invalid alarm list; using an empty list")
            entries = []
        seen_ids = set()
        for entry in entries:
            try:
                alarm = Alarm.from_dict(entry)
            except (ValueError, TypeError, OverflowError):
                logging.getLogger(__name__).warning("Skipping invalid alarm entry")
                continue
            if alarm.id in seen_ids:
                alarm.id = uuid4().hex
            seen_ids.add(alarm.id)
            cfg.alarms.append(alarm)
        return cfg

    def save(self) -> None:
        s = _settings()
        s.setValue("font_size", int(self.font_size))
        s.setValue("opacity", float(self.opacity))
        s.setValue("color", str(self.color))
        s.setValue("auto_color", bool(self.auto_color))
        s.setValue("auto_color_dark_bg", str(self.auto_color_dark_bg))
        s.setValue("auto_color_light_bg", str(self.auto_color_light_bg))
        s.setValue("show_seconds", bool(self.show_seconds))
        s.setValue("show_date", bool(self.show_date))
        s.setValue("click_through", bool(self.click_through))
        s.setValue("start_on_boot", bool(self.start_on_boot))
        s.setValue("sound_mode", sound.normalize_mode(self.sound_mode))
        s.setValue("sound_system_alias", str(self.sound_system_alias))
        s.setValue("sound_custom_path", str(self.sound_custom_path))
        s.setValue("ring_when_screen_off", bool(self.ring_when_screen_off))
        s.setValue("pos_x", "" if self.pos_x is None else int(self.pos_x))
        s.setValue("pos_y", "" if self.pos_y is None else int(self.pos_y))
        s.setValue("alarm_popup_text_color", str(self.alarm_popup_text_color))
        s.setValue(
            "alarm_popup_background_color",
            str(self.alarm_popup_background_color),
        )
        s.setValue(
            "alarm_popup_background_opacity",
            float(self.alarm_popup_background_opacity),
        )
        s.setValue(
            "alarm_popup_flash_enabled",
            bool(self.alarm_popup_flash_enabled),
        )
        s.setValue("alarm_popup_font_scale", float(self.alarm_popup_font_scale))
        s.setValue(
            "alarm_popup_layout",
            _normalize_popup_layout(self.alarm_popup_layout),
        )
        s.setValue("alarms", json.dumps([a.to_dict() for a in self.alarms]))
        s.sync()


def _normalize_popup_layout(value) -> str:
    """Coerce the alarm popup layout setting; invalid falls back to label-above-time."""
    value = str(value or POPUP_LAYOUT_LABEL_TIME)
    return value if value in POPUP_LAYOUTS else POPUP_LAYOUT_LABEL_TIME
