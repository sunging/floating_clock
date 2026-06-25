"""闹钟数据模型与触发管理。"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime
from typing import Callable, Optional

REPEAT_ONCE = "once"
REPEAT_DAILY = "daily"
REPEAT_WEEKDAYS = "weekdays"
REPEAT_CUSTOM = "custom"

REPEAT_TYPES = {
    REPEAT_ONCE,
    REPEAT_DAILY,
    REPEAT_WEEKDAYS,
    REPEAT_CUSTOM,
}

WEEKDAY_NAMES = ("周一", "周二", "周三", "周四", "周五", "周六", "周日")
WORKDAY_INDICES = [0, 1, 2, 3, 4]


@dataclass
class Alarm:
    """单个闹钟。

    time: "HH:MM" 24 小时格式。
    label: 闹钟名称。
    content: 响铃时显示的详细内容。
    enabled: 是否启用。
    repeat_type: 重复类型，支持单次、每天、工作日、自定义星期。
    repeat_weekdays: 自定义星期，0-6 表示周一到周日。
    """

    time: str = "08:00"
    label: str = "闹钟"
    content: str = ""
    enabled: bool = True
    repeat_type: str = REPEAT_DAILY
    repeat_weekdays: list[int] = field(default_factory=list)

    def to_dict(self) -> dict:
        data = asdict(self)
        data["repeat_type"] = _normalize_repeat_type(data["repeat_type"])
        data["repeat_weekdays"] = _normalize_weekdays(data["repeat_weekdays"])
        return data

    @classmethod
    def from_dict(cls, data: dict) -> "Alarm":
        repeat_type = data.get("repeat_type")
        if repeat_type is None:
            repeat_type = (
                REPEAT_DAILY
                if _to_bool(data.get("repeat_daily", True))
                else REPEAT_ONCE
            )

        return cls(
            time=str(data.get("time", "08:00")),
            label=str(data.get("label", "闹钟")),
            content=str(data.get("content", "")),
            enabled=_to_bool(data.get("enabled", True)),
            repeat_type=_normalize_repeat_type(repeat_type),
            repeat_weekdays=_normalize_weekdays(
                data.get("repeat_weekdays", [])
            ),
        )

    def __post_init__(self) -> None:
        self.repeat_type = _normalize_repeat_type(self.repeat_type)
        self.repeat_weekdays = _normalize_weekdays(self.repeat_weekdays)

    def matches(self, now: datetime) -> bool:
        """判断指定时间是否命中当前闹钟。"""
        if not self.enabled or self.time != now.strftime("%H:%M"):
            return False

        weekday = now.weekday()
        if self.repeat_type in (REPEAT_ONCE, REPEAT_DAILY):
            return True
        if self.repeat_type == REPEAT_WEEKDAYS:
            return weekday in WORKDAY_INDICES
        if self.repeat_type == REPEAT_CUSTOM:
            return weekday in self.repeat_weekdays
        return False

    def is_once(self) -> bool:
        """是否为触发后自动停用的单次闹钟。"""
        return self.repeat_type == REPEAT_ONCE


class AlarmManager:
    """持有闹钟列表，按分钟匹配并通过回调触发。"""

    def __init__(self, on_trigger: Callable[[Alarm], None]):
        self._on_trigger = on_trigger
        self.alarms: list[Alarm] = []
        # 记录"上一次触发的分钟键"，避免同一分钟内重复触发。
        self._last_fired_minute: Optional[str] = None

    def set_alarms(self, alarms: list[Alarm]) -> None:
        self.alarms = list(alarms)

    def check(self, now: Optional[datetime] = None) -> None:
        """每个 tick 调用一次；命中启用的闹钟时触发回调。"""
        now = now or datetime.now()
        minute_key = now.strftime("%Y-%m-%d %H:%M")

        # 同一分钟只处理一次，防止 500ms tick 多次触发。
        if minute_key == self._last_fired_minute:
            return

        for alarm in self.alarms:
            if alarm.matches(now):
                self._last_fired_minute = minute_key
                if alarm.is_once():
                    alarm.enabled = False
                self._on_trigger(alarm)
                # 一分钟内只触发一个闹钟，避免多声叠加。
                break


def _normalize_repeat_type(value: str) -> str:
    """把重复类型规整到支持的取值。"""
    value = str(value or REPEAT_DAILY)
    if value in REPEAT_TYPES:
        return value
    return REPEAT_DAILY


def _normalize_weekdays(value) -> list[int]:
    """规整星期列表，忽略非法项并去重排序。"""
    if value is None:
        return []
    days: set[int] = set()
    for item in value:
        try:
            day = int(item)
        except (TypeError, ValueError):
            continue
        if 0 <= day <= 6:
            days.add(day)
    return sorted(days)


def _to_bool(value) -> bool:
    """兼容旧 JSON 里可能出现的字符串布尔值。"""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)
