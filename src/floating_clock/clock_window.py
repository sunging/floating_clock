"""浮动时钟窗口：显示、拖动、鼠标穿透、闪烁提醒。"""

from __future__ import annotations

import sys
from datetime import datetime
from statistics import median
from typing import Callable, Optional

from PySide6.QtCore import Qt, QTimer
from PySide6.QtGui import QColor, QFont, QGuiApplication
from PySide6.QtWidgets import QLabel, QWidget

from floating_clock.config import Config

# Win32 常量（仅 Windows 使用）
_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020


class ClockWindow(QWidget):
    """无边框、置顶、半透明的时钟窗口。"""

    def __init__(
        self,
        config: Config,
        on_clicked: Optional[Callable[[], None]] = None,
        on_moved: Optional[Callable[[], None]] = None,
    ):
        super().__init__()
        self.config = config
        self._on_clicked = on_clicked
        self._on_moved = on_moved
        self._drag_offset = None
        self._dragged = False
        self._move_hint = False
        self._auto_color_value: Optional[str] = None  # 自动模式下计算出的当前文字色

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
        self._alarm_active = False
        self._alarm_title = ""
        self._alarm_content = ""
        self._preview_timer = QTimer(self)
        self._preview_timer.setSingleShot(True)
        self._preview_timer.timeout.connect(self.stop_flashing)

        self.apply_config(config)
        self.update_time()

    # ---- 外观 ----
    def apply_config(self, config: Config) -> None:
        """把配置应用到窗口（字号、颜色、透明度、穿透、位置）。"""
        self.config = config
        self._apply_font(config.font_size)
        if config.auto_color:
            self._auto_color_value = (
                self._compute_auto_color() or self._auto_color_value
            )
        else:
            self._auto_color_value = None
        self._apply_label_style(self._text_color())
        self.setWindowOpacity(config.opacity)
        if self._alarm_active:
            self._render_alarm_popup()
        else:
            self.update_time()
        self._fit()

        if config.pos_x is not None and config.pos_y is not None:
            self.move(config.pos_x, config.pos_y)
        self._clamp_to_screen()

        self.set_click_through(config.click_through)

    def _text_color(self) -> str:
        """当前应使用的文字颜色：自动模式下用计算值，否则用用户设定色。"""
        if self.config.auto_color and self._auto_color_value:
            return self._auto_color_value
        return self.config.color

    def _apply_color(self, color: str) -> None:
        self._apply_label_style(color)

    # ---- 自动适配背景色 ----
    def _sample_background_luminance(self) -> Optional[float]:
        """抓取时钟正后方屏幕区域，返回其中位数感知亮度（0–255）。

        窗口背景透明，仅字形像素是自身干扰；降采样后取中位数可稳健忽略。
        抓屏在部分平台受限，失败时返回 None 由调用方回退到手动颜色。
        """
        try:
            screen = self._current_screen()
            if screen is None:
                return None
            geo = self.frameGeometry()
            pixmap = screen.grabWindow(
                0, geo.x(), geo.y(), geo.width(), geo.height()
            )
            if pixmap.isNull():
                return None
            image = pixmap.toImage().scaled(
                8, 8, Qt.IgnoreAspectRatio, Qt.SmoothTransformation
            )
            lums = []
            for y in range(image.height()):
                for x in range(image.width()):
                    c = image.pixelColor(x, y)
                    lums.append(
                        0.299 * c.red() + 0.587 * c.green() + 0.114 * c.blue()
                    )
            if not lums:
                return None
            return median(lums)
        except Exception:
            # 抓屏是增强功能，失败不应让程序崩溃。
            return None

    def _compute_auto_color(self) -> Optional[str]:
        """根据背景亮度选择浅色/深色文字；无法采样时返回 None。"""
        lum = self._sample_background_luminance()
        if lum is None:
            return None
        if lum > 140:  # 背景偏亮 → 用深色文字
            return self.config.auto_color_light_bg
        return self.config.auto_color_dark_bg

    def update_auto_color(self) -> None:
        """重新采样背景并在颜色变化时更新文字（供主循环/拖动后调用）。"""
        if not self.config.auto_color or self._alarm_active:
            return
        new = self._compute_auto_color()
        if new and new != self._auto_color_value:
            self._auto_color_value = new
            self._apply_label_style(self._text_color())
            self._fit()

    def _apply_label_style(
        self,
        color: str,
        background_color: Optional[str] = None,
        background_opacity: float = 0.0,
    ) -> None:
        border = "border: 2px dashed #2D6CDF;" if self._move_hint else ""
        background = "background: transparent;"
        padding = ""
        if background_color and background_opacity > 0:
            rgba = _rgba(background_color, background_opacity)
            background = f"background-color: {rgba};"
            padding = "padding: 8px 14px;"
        self._label.setStyleSheet(
            f"color: {color}; {background} {padding} {border}"
        )

    def _apply_font(self, size: int) -> None:
        font = QFont("Segoe UI", max(8, int(size)))
        font.setBold(True)
        self._label.setFont(font)

    def set_move_hint(self, on: bool) -> None:
        """显示/隐藏「可拖动」的虚线边框提示。"""
        self._move_hint = on
        self._apply_color(self._text_color())
        self._fit()

    def _fit(self) -> None:
        self._label.adjustSize()
        self.resize(self._label.size())
        # 尺寸变化后（如闹钟弹出放大）重新约束，避免超出屏幕。
        self._clamp_to_screen()

    # ---- 屏幕边界约束 ----
    def _current_screen(self):
        """返回窗口当前所在屏幕，退化到主屏幕。"""
        screen = self.screen()
        if screen is None:
            screen = QGuiApplication.screenAt(self.frameGeometry().center())
        if screen is None:
            screen = QGuiApplication.primaryScreen()
        return screen

    def _clamp_to_screen(self) -> None:
        """把窗口移动到当前屏幕可用区域内，防止超出边界。"""
        screen = self._current_screen()
        if screen is None:
            return
        area = screen.availableGeometry()
        x, y = self.x(), self.y()
        # 窗口可能比屏幕还大，此时贴左上角即可。
        max_x = max(area.left(), area.left() + area.width() - self.width())
        max_y = max(area.top(), area.top() + area.height() - self.height())
        new_x = min(max(x, area.left()), max_x)
        new_y = min(max(y, area.top()), max_y)
        if (new_x, new_y) != (x, y):
            self.move(new_x, new_y)

    # ---- 时间显示 ----
    def update_time(self) -> None:
        if self._alarm_active:
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
    def start_flashing(
        self,
        label: Optional[str] = None,
        content: Optional[str] = None,
    ) -> None:
        self._preview_timer.stop()
        self._alarm_active = True
        self._alarm_title = label or "闹钟"
        self._alarm_content = content or ""
        self._flash_on = False
        if self.config.alarm_popup_flash_enabled:
            self._flash_timer.start()
            self._toggle_flash()
        else:
            self._flash_timer.stop()
            self._flash_on = True
            self._render_alarm_popup()

    def preview_alarm(self, label: str = "闹钟预览", content: str = "") -> None:
        """临时展示闹钟弹出效果，不播放声音也不改变配置。"""
        self.start_flashing(label, content)
        self._preview_timer.start(2500)

    def stop_flashing(self) -> None:
        self._preview_timer.stop()
        self._flash_timer.stop()
        self._alarm_active = False
        self._alarm_title = ""
        self._alarm_content = ""
        self._apply_font(self.config.font_size)
        self._apply_label_style(self._text_color())
        # 弹出放大时可能被移动过，缩回后恢复用户设定的位置。
        if self.config.pos_x is not None and self.config.pos_y is not None:
            self.move(self.config.pos_x, self.config.pos_y)
        self.update_time()

    def _toggle_flash(self) -> None:
        self._flash_on = not self._flash_on
        self._render_alarm_popup()

    def _render_alarm_popup(self) -> None:
        text_color = (
            self.config.alarm_popup_text_color
            if self._flash_on or not self.config.alarm_popup_flash_enabled
            else self._text_color()
        )
        font_size = int(
            self.config.font_size * self.config.alarm_popup_font_scale
        )
        self._apply_font(font_size)
        self._apply_label_style(
            text_color,
            self.config.alarm_popup_background_color,
            self.config.alarm_popup_background_opacity,
        )
        self._label.setText(
            self._format_alarm_text(self._alarm_title, self._alarm_content)
        )
        self._fit()

    def _format_alarm_text(self, title: str, content: str) -> str:
        main = title
        if content:
            main = f"{title}\n{content}"

        layout = self.config.alarm_popup_layout
        if layout == "label_only":
            return main
        if layout == "time_label":
            return self._format_now() + "\n" + main
        return main + "\n" + self._format_now()

    # ---- 拖动（仅在未穿透时有效）----
    def mousePressEvent(self, event):
        if event.button() == Qt.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            self._dragged = False
            if self._on_clicked is not None:
                self._on_clicked()
            event.accept()

    def mouseMoveEvent(self, event):
        if self._drag_offset is not None and event.buttons() & Qt.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            self._clamp_to_screen()  # 拖动时也限制在屏幕内
            self._dragged = True
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            pos = self.pos()
            self.config.pos_x, self.config.pos_y = pos.x(), pos.y()
            self.config.save()
            self.update_auto_color()  # 拖到新位置后立即按背景重算颜色
            self._drag_offset = None
            # 实际拖动过才通知（纯点击不触发退出移动模式）。
            if self._dragged and self._on_moved is not None:
                self._on_moved()
            self._dragged = False
            event.accept()


def _rgba(color: str, opacity: float) -> str:
    """把十六进制颜色和透明度转换为 Qt 样式表可用的 rgba。"""
    qcolor = QColor(color)
    if not qcolor.isValid():
        qcolor = QColor("#202020")
    alpha = max(0, min(255, int(opacity * 255)))
    return (
        f"rgba({qcolor.red()}, {qcolor.green()}, "
        f"{qcolor.blue()}, {alpha})"
    )
