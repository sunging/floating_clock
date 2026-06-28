"""sound.py 的单元测试：模式规整与跨平台静默降级。"""

import sys

import pytest

from floating_clock import sound


@pytest.mark.parametrize(
    "value,expected",
    [
        ("silent", "silent"),
        ("system", "system"),
        ("custom", "custom"),
        ("", "system"),        # 空 → 默认
        (None, "system"),
        ("nonsense", "system"),  # 非法 → 默认
    ],
)
def test_normalize_mode(value, expected):
    assert sound.normalize_mode(value) == expected


def test_system_sounds_nonempty_and_contains_default():
    aliases = [alias for alias, _name in sound.SYSTEM_SOUNDS]
    assert sound.DEFAULT_SYSTEM_SOUND in aliases


@pytest.mark.skipif(
    sys.platform == "win32", reason="仅验证非 Windows 平台的静默降级"
)
def test_play_and_stop_silent_on_non_windows():
    # 非 Windows 平台应直接返回、不抛异常。
    sound.play("system", "SystemHand", "", loop=True)
    sound.stop()


def test_play_silent_mode_does_not_raise():
    # 无声模式在任意平台都不应抛异常。
    sound.play("silent", "SystemHand", "", loop=True)
    sound.stop()
