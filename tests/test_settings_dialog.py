"""Tests for settings_dialog.py: pure helpers and the dialogs driven headlessly."""

import pytest
from PySide6.QtGui import QColor
from PySide6.QtWidgets import QDialog

from floating_clock import settings_dialog as settings_module
from floating_clock.alarm import (
    REPEAT_CUSTOM,
    REPEAT_DAILY,
    REPEAT_ONCE,
    REPEAT_WEEKDAYS,
    Alarm,
)
from floating_clock.config import Config
from floating_clock.settings_dialog import (
    AlarmEditDialog,
    SettingsDialog,
    _parse_hhmm,
    _repeat_label,
)


@pytest.mark.parametrize(
    "value,expected",
    [
        ("08:30", (8, 30)),
        ("00:00", (0, 0)),
        ("23:59", (23, 59)),
        ("xx", (8, 0)),       # malformed -> default
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


def test_repeat_label_unknown_falls_back_to_daily():
    alarm = Alarm()
    alarm.repeat_type = "nonsense"
    assert _repeat_label(alarm) == "每天"


# ---- AlarmEditDialog ----
def test_alarm_edit_dialog_prefills_and_returns_edits(qapp):
    original = Alarm(
        time="07:05", label="起床", content="x", repeat_type=REPEAT_ONCE, enabled=False
    )
    dlg = AlarmEditDialog(original)
    assert dlg._hour_combo.currentText() == "07"
    assert dlg._minute_combo.currentText() == "05"
    assert dlg._label_edit.text() == "起床"

    dlg._hour_combo.setCurrentIndex(22)
    dlg._minute_combo.setCurrentIndex(30)
    dlg._label_edit.setText("  ")
    dlg._content_edit.setPlainText("  body  ")
    dlg._repeat_combo.setCurrentIndex(dlg._repeat_combo.findData(REPEAT_CUSTOM))
    for i, chk in enumerate(dlg._weekday_checks):
        chk.setChecked(i in (5, 6))
    alarm = dlg.alarm()

    assert alarm is original  # edited in place, id preserved
    assert (alarm.time, alarm.label, alarm.content) == ("22:30", "闹钟", "body")
    assert alarm.repeat_type == REPEAT_CUSTOM
    assert alarm.repeat_weekdays == [5, 6]
    assert alarm.enabled is True


def test_alarm_edit_dialog_weekdays_only_enabled_for_custom(qapp):
    dlg = AlarmEditDialog(Alarm(repeat_type=REPEAT_DAILY))
    assert not dlg._weekday_w.isEnabled()
    # New alarms preselect workdays for the custom picker.
    assert dlg._selected_weekdays() == [0, 1, 2, 3, 4]
    dlg._repeat_combo.setCurrentIndex(dlg._repeat_combo.findData(REPEAT_CUSTOM))
    assert dlg._weekday_w.isEnabled()


def test_alarm_edit_dialog_rejects_custom_without_days(qapp, monkeypatch):
    warnings = []
    monkeypatch.setattr(settings_module.QMessageBox, "warning", lambda *a: warnings.append(a))
    dlg = AlarmEditDialog(Alarm(repeat_type=REPEAT_CUSTOM, repeat_weekdays=[1]))
    for chk in dlg._weekday_checks:
        chk.setChecked(False)
    dlg._validate_and_accept()
    assert warnings
    assert dlg.result() != QDialog.Accepted

    dlg._weekday_checks[0].setChecked(True)
    dlg._validate_and_accept()
    assert dlg.result() == QDialog.Accepted


# ---- SettingsDialog ----
def test_settings_dialog_edits_a_copy(qapp):
    config = Config(font_size=40, alarms=[Alarm(time="06:00")])
    dlg = SettingsDialog(config)
    dlg._font_spin.setValue(90)
    dlg._click_through_chk.setChecked(not config.click_through)
    dlg._alarm_list.item(0).setCheckState(settings_module.Qt.Unchecked)

    result = dlg.result_config()

    assert result is not config
    assert result.font_size == 90
    assert result.click_through is not config.click_through
    assert result.alarms[0].enabled is False
    assert config.font_size == 40  # original untouched
    assert config.alarms[0].enabled is True


def test_preview_only_carries_appearance(qapp):
    previews = []
    config = Config(click_through=True)
    dlg = SettingsDialog(config, on_preview=previews.append)
    dlg._click_through_chk.setChecked(False)
    dlg._seconds_chk.setChecked(not config.show_seconds)

    assert previews[-1].show_seconds is not config.show_seconds
    assert previews[-1].click_through is True  # not a live-preview setting


@pytest.mark.parametrize(
    "attr,button,previews_expected",
    [
        ("_selected_color", "_color_btn", True),
        ("_selected_alarm_bg_color", "_alarm_bg_color_btn", False),
    ],
)
def test_pick_color_updates_value_and_swatch(qapp, monkeypatch, attr, button, previews_expected):
    monkeypatch.setattr(
        settings_module.QColorDialog, "getColor", lambda *a: QColor("#ABCDEF")
    )
    previews = []
    dlg = SettingsDialog(Config(), on_preview=previews.append)
    btn = getattr(dlg, button)
    dlg._pick_color(attr, btn, "title", preview=previews_expected)
    assert getattr(dlg, attr) == "#abcdef"
    assert btn.text() == "#abcdef"
    assert bool(previews) is previews_expected


def test_pick_color_cancel_keeps_value(qapp, monkeypatch):
    monkeypatch.setattr(settings_module.QColorDialog, "getColor", lambda *a: QColor())
    dlg = SettingsDialog(Config(color="#123456"))
    dlg._pick_color("_selected_color", dlg._color_btn, "title")
    assert dlg._selected_color == "#123456"
