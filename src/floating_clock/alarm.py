"""闹钟数据模型与触发管理。"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Callable, Optional


@dataclass
class Alarm:
    """单个闹钟。

    time: "HH:MM" 24 小时格式。
    label: 提醒文字。
    enabled: 是否启用。
    repeat_daily: True 表示每天重复；False 表示触发一次后自动停用。
    """

    time: str = "08:00"
    label: str = "闹钟"
    enabled: bool = True
    repeat_daily: bool = True

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "Alarm":
        return cls(
            time=str(data.get("time", "08:00")),
            label=str(data.get("label", "闹钟")),
            enabled=bool(data.get("enabled", True)),
            repeat_daily=bool(data.get("repeat_daily", True)),
        )


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
        current = now.strftime("%H:%M")
        minute_key = now.strftime("%Y-%m-%d %H:%M")

        # 同一分钟只处理一次，防止 500ms tick 多次触发。
        if minute_key == self._last_fired_minute:
            return

        for alarm in self.alarms:
            if alarm.enabled and alarm.time == current:
                self._last_fired_minute = minute_key
                if not alarm.repeat_daily:
                    alarm.enabled = False
                self._on_trigger(alarm)
                # 一分钟内只触发一个闹钟，避免多声叠加。
                break
