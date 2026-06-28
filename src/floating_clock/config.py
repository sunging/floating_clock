"""配置数据类与持久化（基于 QSettings 的 INI 文件，保存在程序目录的 config 下）。"""

from __future__ import annotations

import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings

from floating_clock.alarm import Alarm

# 配置统一放在程序所在目录的 config 子目录下，与工作目录无关，
# 这样开机自启（工作目录通常是 System32）也能读到同一份配置。
CONFIG_DIRNAME = "config"
CONFIG_FILENAME = "config.ini"


def app_dir() -> Path:
    """返回程序所在目录。

    - 打包为 exe（PyInstaller，``sys.frozen``）时为 exe 所在目录。
    - 以源码运行时为项目根目录（``src`` 的上一级）。
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def config_dir() -> Path:
    """返回配置文件夹（程序目录下的 config/），不存在时创建。"""
    directory = app_dir() / CONFIG_DIRNAME
    directory.mkdir(parents=True, exist_ok=True)
    return directory


def config_path() -> Path:
    """返回配置文件的绝对路径（程序目录下 config/config.ini）。"""
    return config_dir() / CONFIG_FILENAME


def _settings() -> QSettings:
    """以 INI 文件格式打开当前目录下的配置，避免写入注册表。"""
    return QSettings(str(config_path()), QSettings.IniFormat)


@dataclass
class Config:
    """浮动时钟的全部可调设置。"""

    font_size: int = 48
    opacity: float = 0.75          # 0.1–1.0，整体窗口透明度
    color: str = "#FFFFFF"         # 文字颜色（十六进制）
    auto_color: bool = False       # 是否根据背景明暗自动调整文字颜色
    auto_color_dark_bg: str = "#F0F0F0"   # 背景偏暗时使用的（浅色）文字
    auto_color_light_bg: str = "#202020"  # 背景偏亮时使用的（深色）文字
    show_seconds: bool = True
    show_date: bool = False
    click_through: bool = True     # 默认鼠标穿透，不影响下层窗口
    start_on_boot: bool = False    # 开机自启动
    sound_mode: str = "system"     # silent / system / custom
    sound_system_alias: str = "SystemHand"  # 系统提示音别名
    sound_custom_path: str = ""    # 自定义提示音文件（WAV）路径
    ring_when_screen_off: bool = False  # 默认关屏不响铃
    pos_x: Optional[int] = None    # None 表示首次启动时居中/默认位置
    pos_y: Optional[int] = None
    alarm_popup_text_color: str = "#FF3030"
    alarm_popup_background_color: str = "#202020"
    alarm_popup_background_opacity: float = 0.65
    alarm_popup_flash_enabled: bool = True
    alarm_popup_font_scale: float = 1.0
    alarm_popup_layout: str = "label_time"
    alarms: list[Alarm] = field(default_factory=list)

    # ---- 持久化 ----
    @classmethod
    def load(cls) -> "Config":
        s = _settings()
        cfg = cls()
        cfg.font_size = int(s.value("font_size", cfg.font_size))
        cfg.opacity = float(s.value("opacity", cfg.opacity))
        cfg.color = str(s.value("color", cfg.color))
        cfg.auto_color = _to_bool(s.value("auto_color", cfg.auto_color))
        cfg.auto_color_dark_bg = str(
            s.value("auto_color_dark_bg", cfg.auto_color_dark_bg)
        )
        cfg.auto_color_light_bg = str(
            s.value("auto_color_light_bg", cfg.auto_color_light_bg)
        )
        cfg.show_seconds = _to_bool(s.value("show_seconds", cfg.show_seconds))
        cfg.show_date = _to_bool(s.value("show_date", cfg.show_date))
        cfg.click_through = _to_bool(s.value("click_through", cfg.click_through))
        cfg.start_on_boot = _to_bool(s.value("start_on_boot", cfg.start_on_boot))
        cfg.sound_mode = _normalize_sound_mode(
            s.value("sound_mode", cfg.sound_mode)
        )
        cfg.sound_system_alias = str(
            s.value("sound_system_alias", cfg.sound_system_alias)
        )
        cfg.sound_custom_path = str(
            s.value("sound_custom_path", cfg.sound_custom_path)
        )
        cfg.ring_when_screen_off = _to_bool(
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
        cfg.alarm_popup_background_opacity = _clamp_float(
            s.value(
                "alarm_popup_background_opacity",
                cfg.alarm_popup_background_opacity,
            ),
            0.0,
            1.0,
            cfg.alarm_popup_background_opacity,
        )
        cfg.alarm_popup_flash_enabled = _to_bool(
            s.value(
                "alarm_popup_flash_enabled",
                cfg.alarm_popup_flash_enabled,
            )
        )
        cfg.alarm_popup_font_scale = _clamp_float(
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
        cfg.pos_x = int(px) if px not in (None, "") else None
        cfg.pos_y = int(py) if py not in (None, "") else None

        raw = s.value("alarms", "[]")
        try:
            cfg.alarms = [Alarm.from_dict(d) for d in json.loads(raw)]
        except (json.JSONDecodeError, TypeError):
            cfg.alarms = []
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
        s.setValue("sound_mode", _normalize_sound_mode(self.sound_mode))
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


def _to_bool(value) -> bool:
    """QSettings 在某些平台把 bool 读成字符串，这里统一转换。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)


def _clamp_float(value, low: float, high: float, default: float) -> float:
    """读取数值配置并限制范围。"""
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return max(low, min(high, number))


def _normalize_sound_mode(value) -> str:
    """规整提示音模式：silent / system / custom，非法值回退到 system。"""
    value = str(value or "system")
    if value in ("silent", "system", "custom"):
        return value
    return "system"


def _normalize_popup_layout(value) -> str:
    """规整闹钟弹出布局配置。"""
    value = str(value or "label_time")
    if value in ("label_time", "time_label", "label_only"):
        return value
    return "label_time"
