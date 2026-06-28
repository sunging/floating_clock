"""Alarm data model and trigger management."""

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
    """A single alarm.

    time: "HH:MM" in 24-hour format.
    label: alarm name.
    content: detailed text shown when ringing.
    enabled: whether the alarm is active.
    repeat_type: repeat mode — once, daily, weekdays, or custom weekdays.
    repeat_weekdays: custom weekdays, 0-6 for Monday through Sunday.
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
        """Whether the given time hits this alarm."""
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
        """Whether this is a one-shot alarm that disables itself on fire."""
        return self.repeat_type == REPEAT_ONCE


class AlarmManager:
    """Holds the alarm list, matches per minute, and fires via a callback."""

    def __init__(self, on_trigger: Callable[[Alarm], None]):
        self._on_trigger = on_trigger
        self.alarms: list[Alarm] = []
        # Track the last fired minute key to avoid re-firing within a minute.
        self._last_fired_minute: Optional[str] = None

    def set_alarms(self, alarms: list[Alarm]) -> None:
        self.alarms = list(alarms)

    def check(self, now: Optional[datetime] = None) -> None:
        """Call once per tick; fires the callback when an enabled alarm hits."""
        now = now or datetime.now()
        minute_key = now.strftime("%Y-%m-%d %H:%M")

        # Only handle a minute once, so the 500ms tick can't fire repeatedly.
        if minute_key == self._last_fired_minute:
            return

        for alarm in self.alarms:
            if alarm.matches(now):
                self._last_fired_minute = minute_key
                if alarm.is_once():
                    alarm.enabled = False
                self._on_trigger(alarm)
                # Only fire one alarm per minute to avoid overlapping sounds.
                break


def _normalize_repeat_type(value: str) -> str:
    """Coerce the repeat type to a supported value."""
    value = str(value or REPEAT_DAILY)
    if value in REPEAT_TYPES:
        return value
    return REPEAT_DAILY


def _normalize_weekdays(value) -> list[int]:
    """Normalize the weekday list, dropping invalid items and dedup-sorting."""
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
    """Tolerate string booleans that may appear in legacy JSON."""
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("1", "true", "yes", "on")
    return bool(value)
