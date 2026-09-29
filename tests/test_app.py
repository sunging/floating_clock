"""Headless regression tests for display-position restoration."""

import pytest
from datetime import datetime
from unittest.mock import Mock
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QAction, QMouseEvent
from PySide6.QtTest import QSignalSpy, QTest

from floating_clock.app import FloatingClockApp
from floating_clock.alarm import Alarm
from floating_clock.config import Config
from floating_clock.screen import ScreenStateMonitor
from floating_clock.settings_dialog import SettingsDialog


@pytest.fixture
def controller(qapp, temp_config_dir, monkeypatch):
    def build_tray(self):
        self.tray = Mock()
        self._stop_action = QAction(qapp)
        self._lock_action = QAction(qapp)
        self._lock_action.setCheckable(True)
        self._lock_action.setChecked(self.config.click_through)
        self._lock_action.toggled.connect(self._toggle_click_through)
        self._move_action = QAction(qapp)
        self._move_action.setCheckable(True)
        self._move_action.toggled.connect(self._toggle_move_mode)
    monkeypatch.setattr(FloatingClockApp, "_build_tray", build_tray)
    monkeypatch.setattr("floating_clock.app.sound.play", Mock())
    monkeypatch.setattr("floating_clock.app.sound.stop", Mock())
    monkeypatch.setattr("floating_clock.app.autostart.set_enabled", lambda enabled: enabled)
    monkeypatch.setattr(ScreenStateMonitor, "start", lambda self, hwnd: False)
    Config(pos_x=20, pos_y=20, click_through=False).save()
    controller = FloatingClockApp(qapp)
    controller.timer.stop()
    qapp.processEvents()
    controller._position_restore_timer.stop()
    yield controller
    controller._position_restore_timer.stop()
    qapp.screenAdded.disconnect(controller._on_screen_added)
    qapp.screenRemoved.disconnect(controller._schedule_position_restore)
    qapp.primaryScreenChanged.disconnect(controller._schedule_position_restore)
    for screen in qapp.screens():
        screen.geometryChanged.disconnect(controller._schedule_position_restore)
        screen.availableGeometryChanged.disconnect(controller._schedule_position_restore)
    controller.clock.windowHandle().screenChanged.disconnect(
        controller._schedule_position_restore
    )
    qapp.removeNativeEventFilter(controller.screen_monitor)
    controller.clock.stop_flashing()
    controller.clock.close()
    controller.clock.deleteLater()
    controller._position_restore_timer.deleteLater()
    for action in (controller._stop_action, controller._lock_action, controller._move_action):
        action.deleteLater()


def _mouse_event(clock, kind, global_pos):
    moving = kind == QEvent.MouseMove
    return QMouseEvent(
        kind,
        QPointF(clock.mapFromGlobal(global_pos)),
        QPointF(global_pos),
        Qt.NoButton if moving else Qt.LeftButton,
        Qt.NoButton if kind == QEvent.MouseButtonRelease else Qt.LeftButton,
        Qt.NoModifier,
    )


def test_position_restore_waits_for_drag_release(controller):
    clock = controller.clock
    press_pos = clock.pos() + QPoint(10, 10)
    assert not clock.is_dragging
    clock.mousePressEvent(_mouse_event(clock, QEvent.MouseButtonPress, press_pos))
    assert clock.is_dragging  # A held press must be protected before movement too.
    target = QPoint(150, 150)
    release_pos = target + QPoint(10, 10)
    clock.mouseMoveEvent(_mouse_event(clock, QEvent.MouseMove, release_pos))
    assert clock.pos() == target

    controller._restore_clock_position()
    assert clock.pos() == target
    assert (clock.config.pos_x, clock.config.pos_y) == (20, 20)
    assert controller._position_restore_timer.isActive()

    clock.mouseReleaseEvent(_mouse_event(clock, QEvent.MouseButtonRelease, release_pos))
    assert not clock.is_dragging
    saved = Config.load()
    assert (saved.pos_x, saved.pos_y) == (target.x(), target.y())
    spy = QSignalSpy(controller._position_restore_timer.timeout)
    assert spy.wait(2000)
    assert clock.pos() == target
    assert not controller._position_restore_timer.isActive()


def test_position_restore_defers_while_press_is_held(controller, monkeypatch):
    clock = controller.clock
    press_pos = clock.pos() + QPoint(10, 10)
    clock.mousePressEvent(_mouse_event(clock, QEvent.MouseButtonPress, press_pos))
    restored = []
    monkeypatch.setattr(clock, "restore_position", lambda: restored.append(True))
    for _ in range(2):
        controller._position_restore_timer.stop()
        controller._restore_clock_position()
        assert controller._position_restore_timer.isActive()
    assert restored == []
    clock.mouseReleaseEvent(_mouse_event(clock, QEvent.MouseButtonRelease, press_pos))
    controller._restore_clock_position()
    assert restored == [True]


def test_display_events_debounce_and_restore_without_drag(controller):
    timer = controller._position_restore_timer
    assert timer.isSingleShot()
    assert timer.interval() == 750
    controller.clock.move(150, 150)
    spy = QSignalSpy(timer.timeout)
    controller._schedule_position_restore()
    QTest.qWait(400)
    controller._schedule_position_restore()
    QTest.qWait(400)
    assert spy.count() == 0
    assert spy.wait(2000)
    assert spy.count() == 1
    assert controller.clock.pos() == QPoint(20, 20)
    assert not timer.isActive()


@pytest.mark.parametrize("preference", [False, True])
@pytest.mark.parametrize("stop_move_first", [False, True])
def test_temporary_click_through_preserves_preference(controller, monkeypatch, preference, stop_move_first):
    applied = []
    monkeypatch.setattr(controller.clock, "set_click_through", applied.append)
    controller._toggle_click_through(preference)
    controller._move_action.setChecked(True)
    alarm = Alarm(time="08:00", repeat_type="once")
    controller.config.alarms = [alarm]
    controller.alarm_manager.set_alarms([alarm])
    controller.alarm_manager.check(datetime(2026, 9, 26, 8, 0))
    assert applied[-1] is False
    assert Config.load().click_through is preference
    if stop_move_first:
        controller._move_action.setChecked(False)
    else:
        controller._stop_alarm()
    assert applied[-1] is False
    if stop_move_first:
        controller._stop_alarm()
    else:
        controller._move_action.setChecked(False)
    assert applied[-1] is preference
    assert controller.config.click_through is preference
    assert Config.load().click_through is preference


def test_changing_preference_while_ringing_keeps_popup_interactive(controller, monkeypatch):
    applied = []
    monkeypatch.setattr(controller.clock, "set_click_through", applied.append)
    controller._on_alarm(Alarm())
    controller._toggle_click_through(True)
    assert applied[-1] is False
    assert Config.load().click_through is True
    controller._stop_alarm()
    assert applied[-1] is True


@pytest.mark.parametrize("accepted", [False, True])
def test_settings_preserve_consumed_alarm(controller, monkeypatch, accepted):
    alarm = Alarm(time="08:00", repeat_type="once")
    controller.config.alarms = [alarm]
    controller.alarm_manager.set_alarms([alarm])
    controller.config.click_through = True
    controller.config.save()
    def edit(dialog):
        dialog._font_spin.setValue(99)
        controller.alarm_manager.check(datetime(2026, 9, 26, 8, 0))
        assert dialog._alarm_list.item(0).checkState() == Qt.Unchecked
        return SettingsDialog.Accepted if accepted else SettingsDialog.Rejected
    monkeypatch.setattr(SettingsDialog, "exec", edit)
    controller._open_settings()
    assert controller.config.font_size == (99 if accepted else 48)
    assert not controller.config.alarms[0].enabled
    assert not controller.alarm_manager.alarms[0].enabled
    controller._toggle_click_through(False)  # An unrelated save must not revive it.
    assert not Config.load().alarms[0].enabled
    assert controller.clock.config is controller.config
    controller._stop_alarm()
    controller.alarm_manager.check(datetime(2026, 9, 27, 8, 0))
    assert not controller._ringing


@pytest.mark.parametrize("edit_kind", ["reenable", "reschedule", "rename", "replace"])
def test_settings_keep_explicit_alarm_edits(controller, monkeypatch, edit_kind):
    alarm = Alarm(time="08:00", repeat_type="once")
    controller.config.alarms = [alarm]
    controller.alarm_manager.set_alarms([alarm])
    def edit(dialog):
        item = dialog._alarm_list.item(0)
        edited = item.data(Qt.UserRole)
        if edit_kind == "reschedule":
            edited.time = "09:00"
            item.setData(Qt.UserRole, edited)
        if edit_kind == "rename":
            edited.label = "改名"
            item.setData(Qt.UserRole, edited)
        if edit_kind == "replace":
            dialog._alarm_list.takeItem(0)
            dialog._add_alarm_item(Alarm(time="08:00", repeat_type="once"))
        controller.alarm_manager.check(datetime(2026, 9, 26, 8, 0))
        if edit_kind == "reenable":
            item.setCheckState(Qt.Checked)
        return SettingsDialog.Accepted
    monkeypatch.setattr(SettingsDialog, "exec", edit)
    controller._open_settings()
    result = controller.config.alarms[0]
    assert result.enabled is (edit_kind != "rename")
    assert Config.load().alarms[0].enabled == result.enabled
    if edit_kind == "reschedule":
        assert result.time == "09:00"
    if edit_kind == "rename":
        assert result.label == "改名"
    assert (result.id == alarm.id) is (edit_kind != "replace")


def test_popup_stop_button_stops_alarm_and_restores_preference(controller, qapp):
    controller.config.click_through = True
    controller._on_alarm(Alarm(content="Long text " * 200))
    qapp.processEvents()
    QTest.mouseClick(controller.clock._stop_button, Qt.LeftButton)
    assert not controller._ringing
    assert not controller.clock._alarm_active
    assert controller.config.click_through


def test_settings_consumes_only_the_matching_alarm_id(controller, monkeypatch):
    alarms = [Alarm(time="08:00", repeat_type="once") for _ in range(2)]
    controller.config.alarms = alarms
    controller.alarm_manager.set_alarms(alarms)
    def edit(dialog):
        controller.alarm_manager.check(datetime(2026, 9, 26, 8, 0))
        assert dialog._alarm_list.item(0).checkState() == Qt.Unchecked
        assert dialog._alarm_list.item(1).checkState() == Qt.Checked
        return SettingsDialog.Accepted
    monkeypatch.setattr(SettingsDialog, "exec", edit)
    controller._open_settings()
    assert [a.enabled for a in Config.load().alarms] == [False, True]


def test_drag_in_move_mode_saves_original_preference(controller):
    controller._toggle_click_through(True)
    controller._move_action.setChecked(True)
    clock = controller.clock
    press = clock.pos() + QPoint(10, 10)
    clock.mousePressEvent(_mouse_event(clock, QEvent.MouseButtonPress, press))
    release = QPoint(160, 160)
    clock.mouseMoveEvent(_mouse_event(clock, QEvent.MouseMove, release))
    clock.mouseReleaseEvent(_mouse_event(clock, QEvent.MouseButtonRelease, release))
    assert not controller._move_mode
    assert not controller._move_action.isChecked()
    assert Config.load().click_through is True
    assert (Config.load().pos_x, Config.load().pos_y) == (150, 150)
