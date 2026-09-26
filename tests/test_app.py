"""Headless regression tests for display-position restoration."""

import pytest
from PySide6.QtCore import QEvent, QPoint, QPointF, Qt
from PySide6.QtGui import QMouseEvent
from PySide6.QtTest import QSignalSpy, QTest

from floating_clock.app import FloatingClockApp
from floating_clock.config import Config
from floating_clock.screen import ScreenStateMonitor


@pytest.fixture
def controller(qapp, temp_config_dir, monkeypatch):
    monkeypatch.setattr(FloatingClockApp, "_build_tray", lambda self: None)
    monkeypatch.setattr(FloatingClockApp, "_on_clock_clicked", lambda self: None)
    monkeypatch.setattr(FloatingClockApp, "_on_clock_moved", lambda self: None)
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
    controller.clock.close()
    controller.clock.deleteLater()
    controller._position_restore_timer.deleteLater()


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
