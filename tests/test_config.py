"""Unit tests for config.py: pure helpers and the save/load roundtrip."""

import sys
import json
from pathlib import Path
from PySide6.QtCore import QSettings
from floating_clock import config as config_module

import pytest

from floating_clock.alarm import REPEAT_CUSTOM, REPEAT_WEEKDAYS, Alarm
from floating_clock.config import (
    Config,
    config_path as original_config_path,
    _clamp_float,
    _is_installed,
    _normalize_popup_layout,
    _normalize_sound_mode,
    _to_bool,
    _user_base_dir,
)


def test_config_fixture_protects_imported_path_alias(temp_config_dir):
    # A pre-imported function must also stay away from the real user directory.
    assert Path(temp_config_dir) in original_config_path().parents
    assert config_module.config_path().parent == Path(temp_config_dir)


@pytest.mark.parametrize("key,value,expected", [
    ("font_size", "bad", 48), ("font_size", "inf", 48),
    ("font_size", -1, 8), ("font_size", 10000, 400),
    ("opacity", "bad", 0.75), ("opacity", "nan", 0.75),
    ("opacity", "inf", 0.75), ("opacity", "-inf", 0.75),
    ("opacity", -1, 0.1), ("opacity", 2, 1.0),
    ("pos_x", "bad", None), ("pos_y", "inf", None),
    ("pos_x", "999999999999999999999999", None), ("pos_x", -1920, -1920),
    ("alarm_popup_font_scale", "nan", 1.0),
    ("alarm_popup_background_opacity", "inf", 0.65),
])
def test_invalid_numeric_settings_are_safe(temp_config_dir, key, value, expected):
    settings = QSettings(str(config_module.config_path()), QSettings.IniFormat)
    settings.setValue(key, value)
    settings.sync()
    assert getattr(Config.load(), key) == expected


@pytest.mark.parametrize("raw", ["bad", "null", "{}", "42", '"text"', "[null]"])
def test_invalid_alarm_list_does_not_stop_loading(temp_config_dir, raw):
    settings = QSettings(str(config_module.config_path()), QSettings.IniFormat)
    settings.setValue("alarms", raw)
    settings.sync()
    assert Config.load().alarms == []
    assert settings.value("alarms") == raw  # Loading does not overwrite the original.


def test_load_preserves_valid_alarms_and_migrates_ids(temp_config_dir):
    settings = QSettings(str(config_module.config_path()), QSettings.IniFormat)
    entries = [{"time": "07:30", "repeat_daily": False}, None, "bad",
               {"time": "25:00"}, {"time": "08:00", "repeat_weekdays": 123},
               {"time": "09:00", "id": "duplicate"}, {"time": "10:00", "id": "duplicate"}]
    settings.setValue("alarms", json.dumps(entries))
    settings.sync()
    config = Config.load()
    assert [a.time for a in config.alarms] == ["07:30", "08:00", "09:00", "10:00"]
    assert config.alarms[0].is_once()
    assert config.alarms[1].repeat_weekdays == []
    ids = [a.id for a in config.alarms]
    assert len(set(ids)) == 4
    config.save()
    assert [a.id for a in Config.load().alarms] == ids


# ---- Pure helpers ----
@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        ("true", True),
        ("1", True),
        ("on", True),
        ("false", False),
        ("0", False),
        ("", False),
    ],
)
def test_to_bool(value, expected):
    assert _to_bool(value) is expected


def test_clamp_float():
    assert _clamp_float(0.5, 0.0, 1.0, 0.75) == 0.5
    assert _clamp_float(1.5, 0.0, 1.0, 0.75) == 1.0   # clamp to upper bound
    assert _clamp_float(-1, 0.0, 1.0, 0.75) == 0.0    # clamp to lower bound
    assert _clamp_float("bad", 0.0, 1.0, 0.75) == 0.75  # invalid -> default
    assert _clamp_float(None, 0.0, 1.0, 0.75) == 0.75


def test_is_installed():
    # Under site-packages / dist-packages counts as installed.
    assert _is_installed(
        Path("/x/lib/site-packages/floating_clock/config.py")
    )
    assert _is_installed(
        Path("/usr/lib/python3/dist-packages/floating_clock/config.py")
    )
    # A source layout does not count as installed.
    assert not _is_installed(Path("/proj/src/floating_clock/config.py"))


def test_user_base_dir_windows(monkeypatch):
    monkeypatch.setattr(sys, "platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\me\AppData\Roaming")
    assert _user_base_dir() == Path(r"C:\Users\me\AppData\Roaming\FloatingClock")


def test_user_base_dir_xdg(monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/me/.config")
    assert _user_base_dir() == Path("/home/me/.config/floating_clock")


def test_normalize_sound_mode():
    assert _normalize_sound_mode("silent") == "silent"
    assert _normalize_sound_mode("system") == "system"
    assert _normalize_sound_mode("custom") == "custom"
    assert _normalize_sound_mode("nonsense") == "system"
    assert _normalize_sound_mode(None) == "system"


def test_normalize_popup_layout():
    assert _normalize_popup_layout("label_time") == "label_time"
    assert _normalize_popup_layout("time_label") == "time_label"
    assert _normalize_popup_layout("label_only") == "label_only"
    assert _normalize_popup_layout("nonsense") == "label_time"
    assert _normalize_popup_layout(None) == "label_time"


# ---- Save/load roundtrip ----
def test_save_load_roundtrip(temp_config_dir):
    cfg = Config(
        font_size=72,
        opacity=0.5,
        color="#123456",
        auto_color=True,
        auto_color_dark_bg="#EEEEEE",
        auto_color_light_bg="#111111",
        show_seconds=False,
        show_date=True,
        click_through=False,
        pos_x=100,
        pos_y=200,
        sound_mode="custom",
        sound_system_alias="SystemAsterisk",
        sound_custom_path=r"C:\sound.wav",
        ring_when_screen_off=True,
        alarm_popup_layout="time_label",
        alarms=[
            Alarm(time="07:30", label="起床", repeat_type=REPEAT_WEEKDAYS),
            Alarm(
                time="22:00",
                label="睡觉",
                repeat_type=REPEAT_CUSTOM,
                repeat_weekdays=[4, 5],
            ),
        ],
    )
    cfg.save()
    loaded = Config.load()

    assert loaded.font_size == 72
    assert loaded.opacity == 0.5
    assert loaded.color == "#123456"
    assert loaded.auto_color is True
    assert loaded.auto_color_dark_bg == "#EEEEEE"
    assert loaded.auto_color_light_bg == "#111111"
    assert loaded.show_seconds is False
    assert loaded.show_date is True
    assert loaded.click_through is False
    assert loaded.pos_x == 100
    assert loaded.pos_y == 200
    assert loaded.sound_mode == "custom"
    assert loaded.sound_system_alias == "SystemAsterisk"
    assert loaded.sound_custom_path == r"C:\sound.wav"
    assert loaded.ring_when_screen_off is True
    assert loaded.alarm_popup_layout == "time_label"

    assert len(loaded.alarms) == 2
    assert loaded.alarms[0].time == "07:30"
    assert loaded.alarms[0].repeat_type == REPEAT_WEEKDAYS
    assert loaded.alarms[1].repeat_weekdays == [4, 5]


def test_load_empty_returns_defaults(temp_config_dir):
    cfg = Config.load()
    defaults = Config()
    assert cfg.font_size == defaults.font_size
    assert cfg.color == defaults.color
    assert cfg.auto_color is defaults.auto_color
    assert cfg.pos_x is None
    assert cfg.alarms == []
