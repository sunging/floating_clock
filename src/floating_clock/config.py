"""配置数据类与持久化（基于 QSettings 的 INI 文件，保存在当前目录）。"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from PySide6.QtCore import QSettings

from floating_clock.alarm import Alarm

# 配置文件保存在程序运行时的当前工作目录下。
CONFIG_FILENAME = "config.ini"


def config_path() -> Path:
    """返回配置文件的绝对路径（当前工作目录下的 config.ini）。"""
    return Path.cwd() / CONFIG_FILENAME


def _settings() -> QSettings:
    """以 INI 文件格式打开当前目录下的配置，避免写入注册表。"""
    return QSettings(str(config_path()), QSettings.IniFormat)


@dataclass
class Config:
    """浮动时钟的全部可调设置。"""

    font_size: int = 48
    opacity: float = 0.75          # 0.1–1.0，整体窗口透明度
    color: str = "#FFFFFF"         # 文字颜色（十六进制）
    show_seconds: bool = True
    show_date: bool = False
    click_through: bool = True     # 默认鼠标穿透，不影响下层窗口
    start_on_boot: bool = False    # 开机自启动
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
        cfg.show_seconds = _to_bool(s.value("show_seconds", cfg.show_seconds))
        cfg.show_date = _to_bool(s.value("show_date", cfg.show_date))
        cfg.click_through = _to_bool(s.value("click_through", cfg.click_through))
        cfg.start_on_boot = _to_bool(s.value("start_on_boot", cfg.start_on_boot))
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
        s.setValue("show_seconds", bool(self.show_seconds))
        s.setValue("show_date", bool(self.show_date))
        s.setValue("click_through", bool(self.click_through))
        s.setValue("start_on_boot", bool(self.start_on_boot))
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


def _normalize_popup_layout(value) -> str:
    """规整闹钟弹出布局配置。"""
    value = str(value or "label_time")
    if value in ("label_time", "time_label", "label_only"):
        return value
    return "label_time"
