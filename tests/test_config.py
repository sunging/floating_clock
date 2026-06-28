"""config.py 的单元测试：纯 helper 与存读往返。"""

import pytest

from floating_clock.alarm import REPEAT_CUSTOM, REPEAT_WEEKDAYS, Alarm
import sys
from pathlib import Path

from floating_clock.config import (
    Config,
    _clamp_float,
    _is_installed,
    _normalize_popup_layout,
    _normalize_sound_mode,
    _to_bool,
    _user_base_dir,
)


# ---- 纯 helper ----
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
    assert _clamp_float(1.5, 0.0, 1.0, 0.75) == 1.0   # 上界裁剪
    assert _clamp_float(-1, 0.0, 1.0, 0.75) == 0.0    # 下界裁剪
    assert _clamp_float("bad", 0.0, 1.0, 0.75) == 0.75  # 非法→default
    assert _clamp_float(None, 0.0, 1.0, 0.75) == 0.75


def test_is_installed():
    # site-packages / dist-packages 内视为已安装。
    assert _is_installed(
        Path("/x/lib/site-packages/floating_clock/config.py")
    )
    assert _is_installed(
        Path("/usr/lib/python3/dist-packages/floating_clock/config.py")
    )
    # 源码布局不算已安装。
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


# ---- 存读往返 ----
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
