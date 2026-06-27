"""settings_dialog.py 模块级纯函数测试（仅需可导入，无需 QApplication）。"""

import pytest

from floating_clock.alarm import (
    REPEAT_CUSTOM,
    REPEAT_DAILY,
    REPEAT_ONCE,
    REPEAT_WEEKDAYS,
    Alarm,
)
from floating_clock.settings_dialog import _parse_hhmm, _repeat_label


@pytest.mark.parametrize(
    "value,expected",
    [
        ("08:30", (8, 30)),
        ("00:00", (0, 0)),
        ("23:59", (23, 59)),
        ("xx", (8, 0)),       # 畸形→默认
        ("", (8, 0)),
        (None, (8, 0)),
    ],
)
def test_parse_hhmm(value, expected):
    assert _parse_hhmm(value) == expected


def test_repeat_label_basic():
    assert _repeat_label(Alarm(repeat_type=REPEAT_ONCE)) == "单次"
    assert _repeat_label(Alarm(repeat_type=REPEAT_DAILY)) == "每天"
    assert _repeat_label(Alarm(repeat_type=REPEAT_WEEKDAYS)) == "工作日"


def test_repeat_label_custom():
    alarm = Alarm(repeat_type=REPEAT_CUSTOM, repeat_weekdays=[0, 2, 6])
    assert _repeat_label(alarm) == "周一、周三、周日"
