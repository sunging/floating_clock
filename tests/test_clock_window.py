"""clock_window.py 辅助函数测试（构造 widget 需 offscreen QApplication）。"""

import pytest

from floating_clock.clock_window import ClockWindow, _rgba
from floating_clock.config import Config


# ---- _rgba（模块级，仅用 QColor 解析）----
def test_rgba_valid():
    assert _rgba("#FF0000", 1.0) == "rgba(255, 0, 0, 255)"


def test_rgba_alpha_from_opacity():
    assert _rgba("#000000", 0.5) == "rgba(0, 0, 0, 127)"


def test_rgba_alpha_clamped():
    assert _rgba("#000000", 2.0).endswith(", 255)")   # 上限
    assert _rgba("#000000", -1.0).endswith(", 0)")     # 下限


def test_rgba_invalid_color_fallback():
    # 非法颜色回落到 #202020 = rgb(32,32,32)
    assert _rgba("not-a-color", 1.0) == "rgba(32, 32, 32, 255)"


# ---- 自动配色（需 qapp 构造 ClockWindow）----
@pytest.fixture
def clock(qapp):
    cfg = Config(
        color="#FFFFFF",
        auto_color=False,  # 构造时不触发真实抓屏
        auto_color_dark_bg="#EEEEEE",
        auto_color_light_bg="#111111",
    )
    return ClockWindow(cfg)


def test_compute_auto_color_bright_bg(clock):
    clock.config.auto_color = True
    clock._sample_background_luminance = lambda: 200.0
    assert clock._compute_auto_color() == "#111111"  # 亮背景→深色文字


def test_compute_auto_color_dark_bg(clock):
    clock.config.auto_color = True
    clock._sample_background_luminance = lambda: 30.0
    assert clock._compute_auto_color() == "#EEEEEE"  # 暗背景→浅色文字


def test_compute_auto_color_sample_failed(clock):
    clock.config.auto_color = True
    clock._sample_background_luminance = lambda: None
    assert clock._compute_auto_color() is None


def test_text_color_prefers_auto_value(clock):
    clock.config.auto_color = True
    clock._auto_color_value = "#EEEEEE"
    assert clock._text_color() == "#EEEEEE"


def test_text_color_falls_back_to_manual(clock):
    clock.config.auto_color = True
    clock._auto_color_value = None
    assert clock._text_color() == "#FFFFFF"
    clock.config.auto_color = False
    clock._auto_color_value = "#EEEEEE"
    assert clock._text_color() == "#FFFFFF"  # 关闭自动时用手动色


# ---- 闹钟弹出文案布局 ----
def test_format_alarm_text_layouts(clock):
    # 固定时间串，避免秒数在断言间跳变导致偶发失败。
    clock._format_now = lambda: "12:34:56"

    clock.config.alarm_popup_layout = "label_only"
    assert clock._format_alarm_text("起床", "内容") == "起床\n内容"

    clock.config.alarm_popup_layout = "time_label"
    assert clock._format_alarm_text("起床", "") == "12:34:56\n起床"

    clock.config.alarm_popup_layout = "label_time"
    assert clock._format_alarm_text("起床", "") == "起床\n12:34:56"
