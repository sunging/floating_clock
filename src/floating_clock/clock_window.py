"""浮动时钟窗口：显示、拖动、鼠标穿透、闪烁提醒。"""

from __future__ import annotations

import sys
from datetime import datetime
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont
from PySide6.QtWidgets import QLabel, QWidget

from floating_clock.config import Config

# Win32 常量（仅 Windows 使用）
_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020


class ClockWindow(QWidget):
    """无边框、置顶、半透明的时钟窗口。"""

    def __init__(self, config: Config, on_clicked: Optional[Callable[[], None]] = None):
        super().__init__()
        self.config = config
        self._on_clicked = on_clicked
        self._drag_offset = None

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool  # 不在任务栏显示
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setTextInteractionFlags(Qt.NoTextInteraction)

        # 闪烁状态
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(450)
        self._flash_timer.timeout.connect(self._toggle_flash)
        self._flash_on = False
        self._flash_text: Optional[str] = None

        self.apply_config(config)
        self.update_time()

    # ---- 外观 ----
    def apply_config(self, config: Config) -> None:
        """把配置应用到窗口（字号、颜色、透明度、穿透、位置）。"""
        self.config = config
        font = QFont("Segoe UI", config.font_size)
        font.setBold(True)
        self._label.setFont(font)
        self._apply_color(config.color)
        self.setWindowOpacity(config.opacity)
        self.update_time()
        self._fit()

        if config.pos_x is not None and config.pos_y is not None:
            self.move(config.pos_x, config.pos_y)

        self.set_click_through(config.click_through)

    def _apply_color(self, color: str) -> None:
        self._label.setStyleSheet(
            f"color: {color}; background: transparent;"
        )

    def _fit(self) -> None:
        self._label.adjustSize()
        self.resize(self._label.size())

    # ---- 时间显示 ----
    def update_time(self) -> None:
        if self._flash_timer.isActive():
            return  # 闪烁期间由 _toggle_flash 控制文字
        self._label.setText(self._format_now())
        self._fit()

    def _format_now(self) -> str:
        now = datetime.now()
        fmt = "%H:%M:%S" if self.config.show_seconds else "%H:%M"
        text = now.strftime(fmt)
        if self.config.show_date:
            text = now.strftime("%Y-%m-%d") + "\n" + text
        return text

    # ---- 鼠标穿透 ----
    def set_click_through(self, enabled: bool) -> None:
        """Windows 上通过扩展窗口样式实现鼠标穿透。"""
        self.config.click_through = enabled
        if sys.platform != "win32":
            return
        try:
            import ctypes

            hwnd = int(self.winId())
            user32 = ctypes.windll.user32
            style = user32.GetWindowLongW(hwnd, _GWL_EXSTYLE)
            if enabled:
                style |= _WS_EX_LAYERED | _WS_EX_TRANSPARENT
            else:
                style &= ~_WS_EX_TRANSPARENT
            user32.SetWindowLongW(hwnd, _GWL_EXSTYLE, style)
        except Exception:
            # 穿透是增强功能，失败不应让程序崩溃。
            pass

    # ---- 闪烁提醒 ----
    def start_flashing(self, label: Optional[str] = None) -> None:
        self._flash_text = label
        self._flash_on = False
        self._flash_timer.start()
        self._toggle_flash()

    def stop_flashing(self) -> None:
        self._flash_timer.stop()
        self._flash_text = None
        self._apply_color(self.config.color)
        self.update_time()

    def _toggle_flash(self) -> None:
        self._flash_on = not self._flash_on
        color = "#FF3030" if self._flash_on else self.config.color
        self._apply_color(color)
        if self._flash_text:
            self._label.setText(self._flash_text + "\n" + self._format_now())
        else:
            self._label.setText(self._format_now())
        self._fit()

    # ---- 拖动（仅在未穿透时有效）----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            if self._on_clicked is not None:
                self._on_clicked()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            pos = self.pos()
            self.config.pos_x, self.config.pos_y = pos.x(), pos.y()
            self.config.save()
            self._drag_offset = None
            event.accept()
