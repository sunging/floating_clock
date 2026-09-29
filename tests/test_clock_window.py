"""Tests for clock_window.py helpers (building widgets needs an offscreen QApplication)."""

import pytest
from PySide6.QtCore import QPoint, QRect, Qt
from PySide6.QtTest import QTest

from floating_clock.clock_window import (
    ClockWindow,
    _clamped_top_left,
    _rgba,
    _screen_for_geometry,
)
from floating_clock.config import Config


# ---- _rgba (module level, only uses QColor parsing) ----
def test_rgba_valid():
    assert _rgba("#FF0000", 1.0) == "rgba(255, 0, 0, 255)"


def test_rgba_alpha_from_opacity():
    assert _rgba("#000000", 0.5) == "rgba(0, 0, 0, 127)"


def test_rgba_alpha_clamped():
    assert _rgba("#000000", 2.0).endswith(", 255)")   # upper bound
    assert _rgba("#000000", -1.0).endswith(", 0)")     # lower bound


def test_rgba_invalid_color_fallback():
    # invalid color falls back to #202020 = rgb(32,32,32)
    assert _rgba("not-a-color", 1.0) == "rgba(32, 32, 32, 255)"


# ---- Multi-screen geometry helpers ----
class FakeScreen:
    def __init__(self, area: QRect):
        self._area = area

    def availableGeometry(self) -> QRect:
        return self._area


def _fake_screen_at(screens):
    def screen_at(point):
        for screen in screens:
            if screen.availableGeometry().contains(point):
                return screen
        return None

    return screen_at


def test_screen_for_geometry_uses_secondary_screen_center():
    primary = FakeScreen(QRect(0, 0, 1920, 1080))
    secondary = FakeScreen(QRect(1920, 0, 1920, 1080))
    screens = [primary, secondary]

    screen = _screen_for_geometry(
        QRect(2100, 100, 300, 100),
        screens,
        _fake_screen_at(screens),
        primary,
    )

    assert screen is secondary


def test_screen_for_geometry_handles_negative_coordinate_screen():
    left = FakeScreen(QRect(-1280, 0, 1280, 1024))
    primary = FakeScreen(QRect(0, 0, 1920, 1080))
    screens = [left, primary]

    screen = _screen_for_geometry(
        QRect(-1200, 200, 300, 100),
        screens,
        _fake_screen_at(screens),
        primary,
    )

    assert screen is left


def test_screen_for_geometry_falls_back_to_largest_intersection():
    primary = FakeScreen(QRect(0, 0, 1920, 1080))
    secondary = FakeScreen(QRect(1920, 0, 1920, 1080))

    screen = _screen_for_geometry(
        QRect(1800, 100, 500, 100),
        [primary, secondary],
        lambda _point: None,
        primary,
    )

    assert screen is secondary


def test_clamped_top_left_keeps_secondary_screen_position():
    area = QRect(1920, 0, 1920, 1080)

    assert _clamped_top_left(QRect(2300, 900, 500, 300), area) == QPoint(2300, 780)


def test_clamped_top_left_pins_oversized_window_to_screen_origin():
    area = QRect(0, 0, 1000, 800)

    assert _clamped_top_left(QRect(100, 100, 2000, 1200), area) == QPoint(0, 0)


def test_configured_position_moves_when_no_clamp_needed(clock):
    secondary = FakeScreen(QRect(1920, 0, 1920, 1080))
    clock.config.pos_x = 2100
    clock.config.pos_y = 120
    clock.resize(200, 80)
    clock._screen_for_geometry = lambda _geometry: secondary

    clock._move_to_configured_position()

    assert clock.pos() == QPoint(2100, 120)


def test_restore_position_reapplies_saved_coordinates(clock):
    secondary = FakeScreen(QRect(1920, 0, 1920, 1080))
    clock.config.pos_x = 2200
    clock.config.pos_y = 160
    clock.resize(200, 80)
    clock._screen_for_geometry = lambda _geometry: secondary
    clock.move(100, 100)  # Simulate Windows relocating it during display wake-up.

    clock.restore_position()

    assert clock.pos() == QPoint(2200, 160)


# ---- Auto color (needs qapp to build ClockWindow) ----
@pytest.fixture
def clock(qapp):
    cfg = Config(
        color="#FFFFFF",
        auto_color=False,  # don't trigger a real screen grab on construction
        auto_color_dark_bg="#EEEEEE",
        auto_color_light_bg="#111111",
    )
    window = ClockWindow(cfg)
    yield window
    window.stop_flashing()
    window.close()
    window.deleteLater()


def test_compute_auto_color_bright_bg(clock):
    clock.config.auto_color = True
    clock._sample_background_luminance = lambda: 200.0
    assert clock._compute_auto_color() == "#111111"  # bright bg -> dark text


def test_compute_auto_color_dark_bg(clock):
    clock.config.auto_color = True
    clock._sample_background_luminance = lambda: 30.0
    assert clock._compute_auto_color() == "#EEEEEE"  # dark bg -> light text


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
    assert clock._text_color() == "#FFFFFF"  # manual color used when auto is off


# ---- Alarm popup text layout ----
def test_format_alarm_text_layouts(clock):
    # Fixed time string, so seconds ticking between asserts can't cause flaky failures.
    clock._format_now = lambda: "12:34:56"

    clock.config.alarm_popup_layout = "label_only"
    assert clock._format_alarm_text("起床", "内容") == "起床\n内容"

    clock.config.alarm_popup_layout = "time_label"
    assert clock._format_alarm_text("起床", "") == "12:34:56\n起床"

    clock.config.alarm_popup_layout = "label_time"
    assert clock._format_alarm_text("起床", "") == "起床\n12:34:56"


@pytest.mark.parametrize("preference", [False, True])
def test_native_click_through_does_not_change_config(clock, preference):
    clock.config.click_through = preference
    clock.set_click_through(not preference)
    assert clock.config.click_through is preference


@pytest.mark.parametrize("flash", [False, True])
@pytest.mark.parametrize("layout", ["label_time", "time_label", "label_only"])
def test_alarm_time_updates_without_changing_flash_phase(clock, flash, layout):
    clock.config.alarm_popup_flash_enabled = flash
    clock.config.alarm_popup_layout = layout
    clock._format_now = lambda: "08:00:00"
    clock.start_flashing("起床", "内容")
    phase = clock._flash_on
    style = clock._alarm_text.styleSheet()
    clock._format_now = lambda: "08:00:10"
    clock.update_time()
    assert ("08:00:10" in clock._alarm_text.toPlainText()) is (layout != "label_only")
    assert "08:00:00" not in clock._alarm_text.toPlainText()
    assert clock._flash_on == phase
    assert clock._alarm_text.styleSheet() == style
    assert clock._flash_timer.isActive() is flash
    clock.stop_flashing()


def test_preview_flash_setting_takes_effect_while_alarm_is_visible(clock):
    clock.config.alarm_popup_flash_enabled = False
    clock.preview_alarm("预览", "内容")
    assert not clock._flash_timer.isActive()
    clock.config.alarm_popup_flash_enabled = True
    clock.apply_config(clock.config)
    assert clock._flash_timer.isActive()
    clock.config.alarm_popup_flash_enabled = False
    clock.apply_config(clock.config)
    assert not clock._flash_timer.isActive()
    assert clock._flash_on
    QTest.mouseClick(clock._stop_button, Qt.LeftButton)
    assert not clock._preview_timer.isActive()


@pytest.mark.parametrize(
    "content",
    ["长内容" * 100, "W" * 120, "一行\n" * 100, "<b>纯文本</b>" * 100],
    ids=["chinese", "unbroken", "multiline", "plain_markup"],
)
@pytest.mark.parametrize("font_size,scale", [(48, 1), (400, 3)])
def test_long_alarm_fits_small_screen_and_can_scroll(clock, qapp, content, font_size, scale):
    area = QRect(-640, 0, 640, 480)
    clock._screen_for_geometry = lambda geometry: FakeScreen(area)
    clock.config.font_size = font_size
    clock.config.alarm_popup_font_scale = scale
    clock.move(-600, 20)
    clock.show()
    clock.start_flashing("提醒", content)
    qapp.processEvents()
    assert area.contains(clock.geometry())
    assert content in clock._alarm_text.toPlainText()
    assert clock.rect().contains(clock._stop_button.geometry().translated(clock._alarm_panel.pos()))
    scroll = clock._alarm_text.verticalScrollBar()
    assert scroll.maximum() > 0
    scroll.setValue(scroll.maximum())
    clock._format_now = lambda: "09:00:00"
    clock.update_time()
    assert scroll.value() == scroll.maximum()
    clock._toggle_flash()
    assert scroll.value() == scroll.maximum()
    QTest.mouseClick(clock._stop_button, Qt.LeftButton)
    assert not clock._alarm_active
    assert clock._alarm_panel.isHidden()
    clock.close()
