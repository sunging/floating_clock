"""程序入口：组装时钟窗口、托盘菜单、定时器与闹钟。"""

from __future__ import annotations

import copy
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

        self.clock = ClockWindow(
            self.config,
            on_clicked=self._on_clock_clicked,
            on_moved=self._on_clock_moved,
        )
        self.clock.show()

        self.alarm_manager = AlarmManager(on_trigger=self._on_alarm)
        self.alarm_manager.set_alarms(self.config.alarms)

        self._ringing = False
        self._auto_color_ticks = 0  # 节流自动调色：每若干个 tick 采样一次

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
        # 双击托盘也可打开设置。
        if reason == QSystemTrayIcon.DoubleClick:
            self._open_settings()

    # ---- 主循环 ----
    def _tick(self) -> None:
        self.clock.update_time()
        self.alarm_manager.check()
        # 抓屏开销较大，约每 2 秒（每 4 个 500ms tick）才重新采样背景色。
        if self.config.auto_color:
            self._auto_color_ticks += 1
            if self._auto_color_ticks >= 4:
                self._auto_color_ticks = 0
                self.clock.update_auto_color()

    # ---- 设置 ----
    def _open_settings(self) -> None:
        # 记录原配置，便于「取消」时回滚实时预览的改动。
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
            # 应用开机自启动到注册表，并以实际结果回写配置。
            self.config.start_on_boot = autostart.set_enabled(
                self.config.start_on_boot
            )
            self.config.save()
            self.clock.apply_config(self.config)
            self.alarm_manager.set_alarms(self.config.alarms)
            self._lock_action.setChecked(self.config.click_through)
        else:
            # 取消：还原预览前的外观。
            if not self._ringing:
                self.clock.stop_flashing()
            self.config = original
            self.clock.apply_config(self.config)

    def _preview_config(self, cfg: Config) -> None:
        """实时预览：把外观改动立即应用到时钟（不落盘）。"""
        self.clock.apply_config(cfg)

    def _preview_alarm_popup(self, cfg: Config) -> None:
        """预览闹钟弹出样式，不播放提示音。"""
        if self._ringing:
            return
        self.clock.apply_config(cfg)
        self.clock.preview_alarm("闹钟预览", "这是闹钟内容预览")

    def _toggle_click_through(self, enabled: bool) -> None:
        self.config.click_through = enabled
        self.clock.set_click_through(enabled)
        self.config.save()

    # ---- 移动模式 ----
    def _toggle_move_mode(self, enabled: bool) -> None:
        if enabled:
            # 临时关闭穿透并显示边框提示，便于拖动。
            self.clock.set_click_through(False)
            self.clock.set_move_hint(True)
            self.tray.showMessage(
                "移动时钟",
                "按住时钟拖到目标位置，松手后自动恢复穿透。",
                _make_icon(),
                4000,
            )
        else:
            # 退出移动模式：去掉提示并恢复用户原来的穿透设置。
            self.clock.set_move_hint(False)
            self.clock.set_click_through(self.config.click_through)

    def _on_clock_moved(self) -> None:
        # 拖动结束后自动退出移动模式（toggled 信号会恢复穿透）。
        if self._move_action.isChecked():
            self._move_action.setChecked(False)

    # ---- 闹钟 ----
    def _on_alarm(self, alarm: Alarm) -> None:
        self._ringing = True
        self._stop_action.setEnabled(True)

        # 响铃时临时关闭穿透并置顶，便于点击消除。
        self.clock.set_click_through(False)
        self.clock.show()
        self.clock.raise_()
        self.clock.activateWindow()
        self.clock.start_flashing(alarm.label, alarm.content)

        _play_sound(loop=True)
        self.tray.showMessage(
            alarm.label,
            alarm.content or alarm.label,
            _make_icon(),
            10000,
        )

        # 单次闹钟触发后已被停用，保存状态。
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
