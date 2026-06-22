"""程序入口：组装时钟窗口、托盘菜单、定时器与闹钟。"""

from __future__ import annotations

import sys

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QAction, QColor, QIcon, QPainter, QPen, QPixmap
from PySide6.QtWidgets import QApplication, QMenu, QMessageBox, QSystemTrayIcon

from floating_clock import autostart
from floating_clock.alarm import Alarm, AlarmManager
from floating_clock.clock_window import ClockWindow
from floating_clock.config import Config
from floating_clock.settings_dialog import SettingsDialog


class FloatingClockApp:
    def __init__(self, app: QApplication):
        self.app = app
        self.config = Config.load()

        # 若已开启自启动，刷新注册表命令（解释器/路径可能已变动）。
        if self.config.start_on_boot and autostart.is_supported():
            autostart.set_enabled(True)

        self.clock = ClockWindow(self.config, on_clicked=self._on_clock_clicked)
        self.clock.show()

        self.alarm_manager = AlarmManager(on_trigger=self._on_alarm)
        self.alarm_manager.set_alarms(self.config.alarms)

        self._ringing = False

        self._build_tray()

        # 主循环：刷新时间并检查闹钟。
        self.timer = QTimer()
        self.timer.setInterval(500)
        self.timer.timeout.connect(self._tick)
        self.timer.start()

    # ---- 托盘 ----
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
        # 双击托盘也可打开设置。
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_settings()

    # ---- 主循环 ----
    def _tick(self) -> None:
        self.clock.update_time()
        self.alarm_manager.check()

    # ---- 设置 ----
    def _open_settings(self) -> None:
        dlg = SettingsDialog(self.config)
        if dlg.exec() == SettingsDialog.Accepted:
            self.config = dlg.result_config()
            # 应用开机自启动到注册表，并以实际结果回写配置。
            self.config.start_on_boot = autostart.set_enabled(
                self.config.start_on_boot
            )
            self.config.save()
            self.clock.apply_config(self.config)
            self.alarm_manager.set_alarms(self.config.alarms)
            self._lock_action.setChecked(self.config.click_through)

    def _toggle_click_through(self, enabled: bool) -> None:
        self.config.click_through = enabled
        self.clock.set_click_through(enabled)
        self.config.save()

    # ---- 闹钟 ----
    def _on_alarm(self, alarm: Alarm) -> None:
        self._ringing = True
        self._stop_action.setEnabled(True)

        # 响铃时临时关闭穿透并置顶，便于点击消除。
        self.clock.set_click_through(False)
        self.clock.show()
        self.clock.raise_()
        self.clock.activateWindow()
        self.clock.start_flashing(alarm.label)

        _play_sound(loop=True)
        self.tray.showMessage("闹钟", alarm.label, _make_icon(), 10000)

        # 单次闹钟触发后已被停用，保存状态。
        if not alarm.repeat_daily:
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
        _play_sound(loop=False)  # 停声
        self.clock.stop_flashing()
        # 恢复用户原来的穿透设置。
        self.clock.set_click_through(self.config.click_through)

    def _quit(self) -> None:
        _play_sound(loop=False)
        self.tray.hide()
        self.app.quit()


def _make_icon() -> QIcon:
    """生成一个简单的时钟托盘图标，避免依赖外部资源文件。"""
    pix = QPixmap(64, 64)
    pix.fill(Qt.transparent)
    painter = QPainter(pix)
    painter.setRenderHint(QPainter.Antialiasing)
    pen = QPen(QColor("#2D6CDF"))
    pen.setWidth(5)
    painter.setPen(pen)
    painter.drawEllipse(6, 6, 52, 52)
    # 指针
    painter.drawLine(32, 32, 32, 14)
    painter.drawLine(32, 32, 46, 38)
    painter.end()
    return QIcon(pix)


def _play_sound(loop: bool) -> None:
    """Windows 上用 winsound 播放/停止提示音；其它平台静默跳过。"""
    if sys.platform != "win32":
        return
    try:
        import winsound

        if loop:
            winsound.PlaySound(
                "SystemHand",
                winsound.SND_ALIAS | winsound.SND_ASYNC | winsound.SND_LOOP,
            )
        else:
            winsound.PlaySound(None, 0)
    except Exception:
        pass


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(False)  # 关闭窗口不退出，靠托盘控制

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
