"""Program entry point: assembles the clock window, tray menu, timer, and alarms."""

from __future__ import annotations

import copy
import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from floating_clock import autostart, sound
from floating_clock.alarm import Alarm, AlarmManager
from floating_clock.clock_window import ClockWindow
from floating_clock.config import Config
from floating_clock.screen import ScreenStateMonitor
from floating_clock.settings_dialog import SettingsDialog


class FloatingClockApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.config = Config.load()

        # If autostart is on, refresh the registry command (interpreter/path may have changed).
        if self.config.start_on_boot and autostart.is_supported():
            autostart.set_enabled(True)

        self.clock = ClockWindow(
            self.config,
            on_clicked=self._on_clock_clicked,
            on_moved=self._on_clock_moved,
        )
        self.clock.show()

        # Monitor display power state for "don't ring when the screen is off".
        self.screen_monitor = ScreenStateMonitor()
        self.app.installNativeEventFilter(self.screen_monitor)
        self.screen_monitor.start(int(self.clock.winId()))

        self.alarm_manager = AlarmManager(on_trigger=self._on_alarm)
        self.alarm_manager.set_alarms(self.config.alarms)

        self._ringing = False
        self._auto_color_ticks = 0  # throttle auto-color: sample every few ticks

        self._build_tray()

        # Main loop: refresh the time and check alarms.
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    # ---- Tray ----
    def _build_tray(self) -> None:
        self.tray = QSystemTrayIcon(_make_icon(), self.app)
        self.tray.setToolTip("浮动时钟")

        menu = QMenu()
        self._settings_action = menu.addAction("设置…")
        self._settings_action.triggered.connect(self._open_settings)

        self._lock_action = QAction("鼠标穿透", menu)
        self._lock_action.setCheckable(True)
        self._lock_action.setChecked(self.config.click_through)
        self._lock_action.toggled.connect(self._toggle_click_through)
        menu.addAction(self._lock_action)

        self._move_action = QAction("移动时钟", menu)
        self._move_action.setCheckable(True)
        self._move_action.toggled.connect(self._toggle_move_mode)
        menu.addAction(self._move_action)

        menu.addSeparator()
        self._stop_action = menu.addAction("停止闹钟")
        self._stop_action.setEnabled(False)
        self._stop_action.triggered.connect(self._stop_alarm)

        menu.addSeparator()
        quit_action = menu.addAction("退出")
        quit_action.triggered.connect(self._quit)

        self.tray.setContextMenu(menu)
        self.tray.activated.connect(self._on_tray_activated)
        self.tray.show()

    def _on_tray_activated(self, reason) -> None:
        # Double-clicking the tray also opens settings.
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_settings()

    # ---- Main loop ----
    def _tick(self) -> None:
        self.clock.update_time()
        # When the screen is off and "ring when screen off" is disabled, skip the
        # alarm check (don't fire, don't consume a one-shot alarm).
        if self._alarms_active():
            self.alarm_manager.check()
        # Grabbing the screen is costly, so re-sample the background only about
        # every 2 seconds (every 4 of the 500ms ticks).
        if self.config.auto_color:
            self._auto_color_ticks += 1
            if self._auto_color_ticks >= 4:
                self._auto_color_ticks = 0
                self.clock.update_auto_color()

    def _alarms_active(self) -> bool:
        """Whether alarms should be checked now (screen on, or ring-when-off allowed)."""
        if self.config.ring_when_screen_off:
            return True
        return not self.screen_monitor.is_display_off()

    # ---- Settings ----
    def _open_settings(self) -> None:
        # Snapshot the original config so "Cancel" can roll back live preview changes.
        original = copy.deepcopy(self.config)
        dlg = SettingsDialog(
            self.config,
            on_preview=self._preview_config,
            on_alarm_preview=self._preview_alarm_popup,
        )
        if dlg.exec() == SettingsDialog.Accepted:
            if not self._ringing:
                self.clock.stop_flashing()
            self.config = dlg.result_config()
            # Apply autostart to the registry and write back the actual result.
            self.config.start_on_boot = autostart.set_enabled(
                self.config.start_on_boot
            )
            self.config.save()
            self.clock.apply_config(self.config)
            self.alarm_manager.set_alarms(self.config.alarms)
            self._lock_action.setChecked(self.config.click_through)
        else:
            # Cancel: restore the appearance from before the preview.
            if not self._ringing:
                self.clock.stop_flashing()
            self.config = original
            self.clock.apply_config(self.config)

    def _preview_config(self, cfg: Config) -> None:
        """Live preview: apply appearance changes to the clock immediately (no save)."""
        self.clock.apply_config(cfg)

    def _preview_alarm_popup(self, cfg: Config) -> None:
        """Preview the alarm popup style without playing a sound."""
        if self._ringing:
            return
        self.clock.apply_config(cfg)
        self.clock.preview_alarm("闹钟预览", "这是闹钟内容预览")

    def _toggle_click_through(self, enabled: bool) -> None:
        self.config.click_through = enabled
        self.clock.set_click_through(enabled)
        self.config.save()

    # ---- Move mode ----
    def _toggle_move_mode(self, enabled: bool) -> None:
        if enabled:
            # Temporarily disable click-through and show a border hint for dragging.
            self.clock.set_click_through(False)
            self.clock.set_move_hint(True)
            self.tray.showMessage(
                "移动时钟",
                "按住时钟拖到目标位置，松手后自动恢复穿透。",
                _make_icon(),
                4000,
            )
        else:
            # Exit move mode: remove the hint and restore the user's click-through setting.
            self.clock.set_move_hint(False)
            self.clock.set_click_through(self.config.click_through)

    def _on_clock_moved(self) -> None:
        # Auto-exit move mode after a drag (the toggled signal restores click-through).
        if self._move_action.isChecked():
            self._move_action.setChecked(False)

    # ---- Alarm ----
    def _on_alarm(self, alarm: Alarm) -> None:
        self._ringing = True
        self._stop_action.setEnabled(True)

        # While ringing, temporarily disable click-through and raise it for click-to-dismiss.
        self.clock.set_click_through(False)
        self.clock.show()
        self.clock.raise_()
        self.clock.activateWindow()
        self.clock.start_flashing(alarm.label, alarm.content)

        sound.play(
            self.config.sound_mode,
            self.config.sound_system_alias,
            self.config.sound_custom_path,
            loop=True,
        )
        self.tray.showMessage(
            alarm.label,
            alarm.content or alarm.label,
            _make_icon(),
            10000,
        )

        # A one-shot alarm is now disabled after firing; persist the state.
        if alarm.is_once():
            self.config.alarms = self.alarm_manager.alarms
            self.config.save()

    def _on_clock_clicked(self) -> None:
        if self._ringing:
            self._stop_alarm()

    def _stop_alarm(self) -> None:
        if not self._ringing:
            return
        self._ringing = False
        self._stop_action.setEnabled(False)
        sound.stop()
        self.clock.stop_flashing()
        # Restore the user's original click-through setting.
        self.clock.set_click_through(self.config.click_through)

    def _quit(self) -> None:
        sound.stop()
        self.tray.hide()
        self.app.quit()


def _make_icon() -> QIcon:
    """Generate a simple clock tray icon, avoiding external resource files."""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#2D6CDF"))
    pen.setWidth(5)
    painter.setPen(pen)
    painter.drawEllipse(6, 6, 52, 52)
    # Hands
    painter.drawLine(32, 32, 32, 14)
    painter.drawLine(32, 32, 46, 38)
    painter.end()
    return QIcon(pix)


def _detach_to_background() -> bool:
    """On Windows, relaunch self as a detached background process, freeing the foreground terminal.

    An environment-variable sentinel avoids infinite relaunching: when already
    the background child, return False and run normally. Non-Windows platforms
    are not handled (returns False).
    """
    import os

    if sys.platform != "win32":
        return False
    if os.environ.get("FLOATING_CLOCK_DETACHED") == "1":
        return False  # already the background child, start normally

    try:
        import subprocess
        from pathlib import Path

        # Prefer pythonw.exe so the child doesn't pop up a console window.
        exe = Path(sys.executable)
        pythonw = exe.with_name("pythonw.exe")
        python = str(pythonw) if pythonw.exists() else sys.executable

        env = dict(os.environ, FLOATING_CLOCK_DETACHED="1")
        # DETACHED_PROCESS severs the current console; CREATE_NO_WINDOW guards against a black box.
        creationflags = 0x00000008 | 0x00000200 | 0x08000000
        subprocess.Popen(
            [python, "-m", "floating_clock", *sys.argv[1:]],
            env=env,
            creationflags=creationflags,
            close_fds=True,
        )
        return True
    except Exception:
        # If backgrounding fails, fall back to running in the foreground.
        return False


def main() -> int:
    if _detach_to_background():
        return 0  # parent exits immediately, returning the foreground terminal

    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # closing windows doesn't quit; tray controls lifecycle

    if not QSystemTrayIcon.isSystemTrayAvailable():
        QMessageBox.warning(
            None,
            "浮动时钟",
            "系统托盘不可用，设置入口将无法显示。",
        )

    FloatingClockApp(app)
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
