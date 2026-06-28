"""Unit tests for alarm.py (pure logic, no Qt needed)."""

from datetime import datetime

import pytest

from floating_clock.alarm import (
    REPEAT_CUSTOM,
    REPEAT_DAILY,
    REPEAT_ONCE,
    REPEAT_WEEKDAYS,
    Alarm,
    AlarmManager,
    _normalize_repeat_type,
    _normalize_weekdays,
    _to_bool,
)

# Fixed time anchors, to avoid depending on the current system time.
MON_0800 = datetime(2024, 1, 1, 8, 0)   # 2024-01-01 is a Monday
SAT_0800 = datetime(2024, 1, 6, 8, 0)   # Saturday
MON_0900 = datetime(2024, 1, 1, 9, 0)


# ---- Alarm.matches ----
def test_matches_once_and_daily_hit():
    assert Alarm(time="08:00", repeat_type=REPEAT_ONCE).matches(MON_0800)
    assert Alarm(time="08:00", repeat_type=REPEAT_DAILY).matches(MON_0800)


def test_matches_wrong_time():
    assert not Alarm(time="08:00", repeat_type=REPEAT_DAILY).matches(MON_0900)


def test_matches_disabled():
    alarm = Alarm(time="08:00", repeat_type=REPEAT_DAILY, enabled=False)
    assert not alarm.matches(MON_0800)


def test_matches_weekdays():
    alarm = Alarm(time="08:00", repeat_type=REPEAT_WEEKDAYS)
    assert alarm.matches(MON_0800)       # Monday hits
    assert not alarm.matches(SAT_0800)   # Saturday doesn't hit


def test_matches_custom():
    # Only Saturday (5) selected
    alarm = Alarm(time="08:00", repeat_type=REPEAT_CUSTOM, repeat_weekdays=[5])
    assert alarm.matches(SAT_0800)
    assert not alarm.matches(MON_0800)


def test_is_once():
    assert Alarm(repeat_type=REPEAT_ONCE).is_once()
    assert not Alarm(repeat_type=REPEAT_DAILY).is_once()


# ---- Serialization roundtrip ----
def test_to_from_dict_roundtrip():
    alarm = Alarm(
        time="07:30",
        label="起床",
        content="该起床了",
        enabled=True,
        repeat_type=REPEAT_CUSTOM,
        repeat_weekdays=[2, 0, 0, 4],  # will be deduped and sorted
    )
    restored = Alarm.from_dict(alarm.to_dict())
    assert restored.time == "07:30"
    assert restored.label == "起床"
    assert restored.content == "该起床了"
    assert restored.enabled is True
    assert restored.repeat_type == REPEAT_CUSTOM
    assert restored.repeat_weekdays == [0, 2, 4]


@pytest.mark.parametrize(
    "legacy_value,expected",
    [(True, REPEAT_DAILY), (False, REPEAT_ONCE), ("true", REPEAT_DAILY)],
)
def test_from_dict_legacy_repeat_daily(legacy_value, expected):
    alarm = Alarm.from_dict({"time": "08:00", "repeat_daily": legacy_value})
    assert alarm.repeat_type == expected


def test_from_dict_missing_keys_defaults():
    alarm = Alarm.from_dict({})
    assert alarm.time == "08:00"
    assert alarm.label == "闹钟"
    assert alarm.repeat_type == REPEAT_DAILY  # no repeat_daily defaults to True -> DAILY


# ---- Normalization functions ----
def test_normalize_weekdays():
    assert _normalize_weekdays([3, 1, 1, 3]) == [1, 3]
    assert _normalize_weekdays([7, -1, 2]) == [2]
    assert _normalize_weekdays(["x", None, 4]) == [4]
    assert _normalize_weekdays(None) == []


def test_normalize_repeat_type():
    assert _normalize_repeat_type(REPEAT_WEEKDAYS) == REPEAT_WEEKDAYS
    assert _normalize_repeat_type("nonsense") == REPEAT_DAILY
    assert _normalize_repeat_type("") == REPEAT_DAILY


@pytest.mark.parametrize(
    "value,expected",
    [
        (True, True),
        (False, False),
        ("true", True),
        ("TRUE", True),
        ("1", True),
        ("yes", True),
        ("on", True),
        ("0", False),
        ("false", False),
        ("", False),
    ],
)
def test_to_bool(value, expected):
    assert _to_bool(value) is expected


# ---- AlarmManager.check ----
def test_manager_dedup_same_minute():
    fired = []
    mgr = AlarmManager(on_trigger=fired.append)
    mgr.set_alarms([Alarm(time="08:00", repeat_type=REPEAT_DAILY)])
    mgr.check(MON_0800)
    mgr.check(MON_0800)  # same minute, the second call doesn't fire again
    assert len(fired) == 1


def test_manager_once_disables_after_fire():
    fired = []
    once = Alarm(time="08:00", repeat_type=REPEAT_ONCE)
    mgr = AlarmManager(on_trigger=fired.append)
    mgr.set_alarms([once])
    mgr.check(MON_0800)
    assert fired == [once]
    assert once.enabled is False


def test_manager_only_first_match_per_minute():
    fired = []
    a = Alarm(time="08:00", label="A", repeat_type=REPEAT_DAILY)
    b = Alarm(time="08:00", label="B", repeat_type=REPEAT_DAILY)
    mgr = AlarmManager(on_trigger=fired.append)
    mgr.set_alarms([a, b])
    mgr.check(MON_0800)
    assert fired == [a]  # only the first match per minute fires
