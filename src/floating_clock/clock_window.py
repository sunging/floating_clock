"""Floating clock window: display, dragging, click-through, flashing reminder."""

from __future__ import annotations

import math
import sys
from datetime import datetime
from statistics import median
from typing import Callable, Optional

from PySide6.QtCore import QPoint, QRect, Qt, QTimer
from PySide6.QtGui import QColor, QFont, QFontMetricsF, QGuiApplication, QTextDocument, QTextOption
from PySide6.QtWidgets import QLabel, QPlainTextEdit, QPushButton, QVBoxLayout, QWidget

from floating_clock.config import (
    POPUP_LAYOUT_LABEL_ONLY,
    POPUP_LAYOUT_TIME_LABEL,
    Config,
)

# Win32 constants (Windows only)
_GWL_EXSTYLE = -20
_WS_EX_LAYERED = 0x00080000
_WS_EX_TRANSPARENT = 0x00000020

_FLASH_INTERVAL_MS = 450  # alarm popup text color toggle period
_PREVIEW_DURATION_MS = 2500  # how long the settings "preview" popup stays up
# Median background luminance (0-255) above which dark text is used in auto-color mode.
_BRIGHT_BG_LUMINANCE = 140

# Alarm popup sizing: fraction of the display it may cover, and the space
# around the text (horizontal/vertical) taken by the text edit's padding/frame.
_POPUP_MAX_SCREEN_FRACTION = 0.8
_POPUP_MIN_WIDTH = 160
_POPUP_H_PADDING = 32
_POPUP_V_PADDING = 24


class ClockWindow(QWidget):
    """Frameless, always-on-top, translucent clock window."""

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
        self._auto_color_value: Optional[str] = None  # current text color computed in auto mode

        self.setWindowFlags(
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool  # don't show in the taskbar
        )
        self.setAttribute(Qt.WA_TranslucentBackground, True)

        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
        self._label.setTextInteractionFlags(Qt.NoTextInteraction)
        self._label.setTextFormat(Qt.PlainText)

        self._alarm_panel = QWidget(self)
        popup_layout = QVBoxLayout(self._alarm_panel)
        popup_layout.setContentsMargins(0, 0, 0, 0)
        popup_layout.setSpacing(4)
        self._alarm_text = QPlainTextEdit(self._alarm_panel)
        self._alarm_text.setReadOnly(True)
        self._alarm_text.setFrameShape(QPlainTextEdit.NoFrame)
        self._alarm_text.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        popup_layout.addWidget(self._alarm_text)
        self._stop_button = QPushButton("停止闹钟", self._alarm_panel)
        self._stop_button.clicked.connect(self._dismiss_popup)
        popup_layout.addWidget(self._stop_button)
        self._alarm_panel.hide()

        # Flashing state
        self._flash_timer = QTimer(self)
        self._flash_timer.setInterval(_FLASH_INTERVAL_MS)
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

    # ---- Appearance ----
    def apply_config(self, config: Config) -> None:
        """Apply config to the window (font, color, opacity, click-through, position)."""
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
            self._sync_flash_timer()
            self._render_alarm_popup()
        else:
            self.update_time()
        self._fit()

        if config.pos_x is not None and config.pos_y is not None:
            self._move_to_configured_position()
        else:
            self._clamp_to_screen()

        self.set_click_through(config.click_through)

    def _text_color(self) -> str:
        """Text color to use now: the computed value in auto mode, else the user's color."""
        if self.config.auto_color and self._auto_color_value:
            return self._auto_color_value
        return self.config.color

    # ---- Auto-adapt to background color ----
    def _sample_background_luminance(self) -> Optional[float]:
        """Return the median perceived luminance (0-255) of the screen behind the clock.

        The window background is transparent, so only glyph pixels are self-noise;
        downsampling then taking the median robustly ignores them. Screen grabs
        are restricted on some platforms; on failure return None so the caller
        falls back to the manual color.
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
            # Screen grabbing is an enhancement; failure must not crash the app.
            return None

    def _compute_auto_color(self) -> Optional[str]:
        """Choose light/dark text by background luminance; None when unsamplable."""
        lum = self._sample_background_luminance()
        if lum is None:
            return None
        if lum > _BRIGHT_BG_LUMINANCE:  # bright background -> use dark text
            return self.config.auto_color_light_bg
        return self.config.auto_color_dark_bg

    def update_auto_color(self) -> None:
        """Re-sample the background and restyle if the text color changed."""
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
        self._alarm_text.setStyleSheet(
            f"QPlainTextEdit {{ color: {color}; {background} padding: 4px; {border} }}"
        )

    def _apply_font(self, size: int) -> None:
        font = QFont("Segoe UI", max(8, int(size)))
        font.setBold(True)
        self._label.setFont(font)
        self._popup_font = font

    def set_move_hint(self, on: bool) -> None:
        """Show/hide the dashed "draggable" border hint."""
        self._move_hint = on
        if self._alarm_active:
            self._render_alarm_popup()
            return
        self._apply_label_style(self._text_color())
        self._fit()

    def _fit(self) -> None:
        if self._alarm_active:
            self._fit_alarm_popup()
            return
        self._label.adjustSize()
        self.resize(self._label.size())
        # Re-clamp after a size change (e.g. the alarm popup enlarges) to stay on screen.
        self._clamp_to_screen()

    def _fit_alarm_popup(self) -> None:
        """Bound the popup to its display; scroll rather than truncate content."""
        screen = self._screen_for_geometry(QRect(self.x(), self.y(), 1, 1))
        if screen is None:
            return
        area = screen.availableGeometry()
        max_width = max(1, int(area.width() * _POPUP_MAX_SCREEN_FRACTION))
        max_height = max(1, int(area.height() * _POPUP_MAX_SCREEN_FRACTION))
        button_height = self._stop_button.sizeHint().height()
        font = QFont(self._popup_font)
        metrics = QFontMetricsF(font)
        text = self._alarm_text.toPlainText()
        widest = max((metrics.horizontalAdvance(c) for c in set(text) if c != "\n"), default=1)
        # Even the largest configured font must leave room for readable glyphs.
        scale = min(
            1.0,
            max(1, max_width - _POPUP_H_PADDING) / max(1, widest),
            max(1, max_height - button_height - _POPUP_V_PADDING) / max(1, metrics.height()),
        )
        if scale < 1:
            font.setPointSizeF(max(1.0, font.pointSizeF() * scale))
            metrics = QFontMetricsF(font)
        if self._alarm_text.font() != font:
            self._alarm_text.setFont(font)
        natural_width = max(
            (metrics.horizontalAdvance(line) for line in text.splitlines()), default=0
        )
        width = min(max_width, max(_POPUP_MIN_WIDTH, math.ceil(natural_width) + _POPUP_H_PADDING))
        document = QTextDocument()
        document.setDefaultFont(font)
        option = document.defaultTextOption()
        option.setWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        document.setDefaultTextOption(option)
        document.setPlainText(text)
        document.setTextWidth(max(1, width - _POPUP_H_PADDING))
        height = min(
            max_height,
            math.ceil(document.size().height()) + button_height + _POPUP_V_PADDING,
        )
        self.resize(width, height)
        self._alarm_panel.setGeometry(self.rect())
        self.move(_clamped_top_left(self._window_geometry(), area))

    # ---- Screen boundary clamping ----
    def _current_screen(self):
        """Return the screen containing the window geometry."""
        return self._screen_for_geometry(self.frameGeometry())

    def _screen_for_geometry(self, geometry: QRect):
        """Return the best screen for a target geometry."""
        return _screen_for_geometry(
            geometry,
            QGuiApplication.screens(),
            QGuiApplication.screenAt,
            QGuiApplication.primaryScreen(),
        )

    def _window_geometry(self) -> QRect:
        return QRect(self.x(), self.y(), self.width(), self.height())

    def _move_to_configured_position(self) -> None:
        if self.config.pos_x is None or self.config.pos_y is None:
            return
        target = QRect(
            self.config.pos_x,
            self.config.pos_y,
            self.width(),
            self.height(),
        )
        self._move_clamped(target)

    def restore_position(self) -> None:
        """Restore the saved position after Windows changes the display layout."""
        if self.config.pos_x is not None and self.config.pos_y is not None:
            self._move_to_configured_position()
        else:
            self._clamp_to_screen()
        if self._alarm_active:
            self._fit()

    def _clamp_to_screen(self) -> None:
        """Move the window into the current screen's available area to avoid overflow."""
        self._move_clamped(self._window_geometry())

    def _move_clamped(self, geometry: QRect) -> None:
        screen = self._screen_for_geometry(geometry)
        if screen is None:
            return
        area = screen.availableGeometry()
        top_left = _clamped_top_left(geometry, area)
        if top_left != self.pos():
            self.move(top_left)

    # ---- Time display ----
    def update_time(self) -> None:
        if self._alarm_active:
            self._update_alarm_text()
            return
        text = self._format_now()
        if self._label.text() != text:
            self._label.setText(text)
            self._fit()

    def _format_now(self) -> str:
        now = datetime.now()
        fmt = "%H:%M:%S" if self.config.show_seconds else "%H:%M"
        text = now.strftime(fmt)
        if self.config.show_date:
            text = now.strftime("%Y-%m-%d") + "\n" + text
        return text

    # ---- Click-through ----
    def set_click_through(self, enabled: bool) -> None:
        """Implement mouse click-through via the extended window style on Windows."""
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
            # Click-through is an enhancement; failure must not crash the app.
            pass

    # ---- Flashing reminder ----
    def start_flashing(
        self,
        label: Optional[str] = None,
        content: Optional[str] = None,
    ) -> None:
        self._preview_timer.stop()
        self._alarm_active = True
        self._alarm_title = label or "闹钟"
        self._alarm_content = content or ""
        self._label.hide()
        self._alarm_panel.show()
        self._stop_button.setText("停止闹钟")
        self._flash_on = True
        self._sync_flash_timer()
        self._render_alarm_popup()
        self._alarm_text.verticalScrollBar().setValue(0)

    def _sync_flash_timer(self) -> None:
        """Keep flash timing independent of time-text refreshes."""
        if self.config.alarm_popup_flash_enabled:
            if not self._flash_timer.isActive():
                self._flash_timer.start()
        else:
            self._flash_timer.stop()
            self._flash_on = True

    def _dismiss_popup(self) -> None:
        if self._on_clicked is not None:
            self._on_clicked()
        if self._alarm_active:
            self.stop_flashing()

    def preview_alarm(self, label: str = "闹钟预览", content: str = "") -> None:
        """Briefly show the alarm popup effect without playing sound or changing config."""
        self.start_flashing(label, content)
        self._stop_button.setText("关闭预览")
        self._preview_timer.start(_PREVIEW_DURATION_MS)

    def stop_flashing(self) -> None:
        self._preview_timer.stop()
        self._flash_timer.stop()
        self._alarm_active = False
        self._alarm_title = ""
        self._alarm_content = ""
        self._alarm_panel.hide()
        self._label.show()
        self._apply_font(self.config.font_size)
        self._apply_label_style(self._text_color())
        # The popup may have been moved when enlarged; restore the user's position after shrinking.
        if self.config.pos_x is not None and self.config.pos_y is not None:
            self.move(self.config.pos_x, self.config.pos_y)
        self.update_time()
        self._fit()

    def _toggle_flash(self) -> None:
        self._flash_on = not self._flash_on
        self._render_alarm_popup()

    def _render_alarm_popup(self) -> None:
        scroll = self._alarm_text.verticalScrollBar()
        offset, at_bottom = scroll.value(), scroll.value() == scroll.maximum()
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
        self._update_alarm_text()
        self._fit()
        scroll.setValue(scroll.maximum() if at_bottom else offset)

    def _update_alarm_text(self) -> None:
        text = self._format_alarm_text(self._alarm_title, self._alarm_content)
        if self._alarm_text.toPlainText() == text:
            return
        scroll = self._alarm_text.verticalScrollBar()
        offset = scroll.value()
        at_bottom = offset == scroll.maximum()
        self._alarm_text.setPlainText(text)
        self._fit()
        scroll.setValue(scroll.maximum() if at_bottom else offset)

    def _format_alarm_text(self, title: str, content: str) -> str:
        main = title
        if content:
            main = f"{title}\n{content}"

        layout = self.config.alarm_popup_layout
        if layout == POPUP_LAYOUT_LABEL_ONLY:
            return main
        if layout == POPUP_LAYOUT_TIME_LABEL:
            return self._format_now() + "\n" + main
        return main + "\n" + self._format_now()

    # ---- Dragging (only when click-through is off) ----
    @property
    def is_dragging(self) -> bool:
        """Whether a mouse press is held, including before the first movement."""
        return self._drag_offset is not None

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
            self._clamp_to_screen()  # also clamp to screen while dragging
            self._dragged = True
            event.accept()

    def mouseReleaseEvent(self, event):
        if self._drag_offset is not None:
            pos = self.pos()
            self.config.pos_x, self.config.pos_y = pos.x(), pos.y()
            self.config.save()
            self.update_auto_color()  # recompute color from the background at the new position
            self._drag_offset = None
            # Only notify on an actual drag (a plain click won't exit move mode).
            if self._dragged and self._on_moved is not None:
                self._on_moved()
            self._dragged = False
            event.accept()


def _rgba(color: str, opacity: float) -> str:
    """Convert a hex color and opacity to an rgba value usable in a Qt stylesheet."""
    qcolor = QColor(color)
    if not qcolor.isValid():
        qcolor = QColor("#202020")
    alpha = max(0, min(255, int(opacity * 255)))
    return (
        f"rgba({qcolor.red()}, {qcolor.green()}, "
        f"{qcolor.blue()}, {alpha})"
    )


def _screen_for_geometry(geometry: QRect, screens, screen_at, fallback):
    """Pick a screen from the target geometry instead of the widget's stale screen."""
    screen = screen_at(geometry.center()) if screen_at is not None else None
    if screen is not None:
        return screen

    best_screen = None
    best_area = 0
    for candidate in screens:
        area = _intersection_area(geometry, candidate.availableGeometry())
        if area > best_area:
            best_screen = candidate
            best_area = area
    if best_screen is not None:
        return best_screen
    return fallback


def _intersection_area(a: QRect, b: QRect) -> int:
    intersection = a.intersected(b)
    if intersection.isEmpty():
        return 0
    return intersection.width() * intersection.height()


def _clamped_top_left(geometry: QRect, area: QRect) -> QPoint:
    """Clamp a window rectangle into a screen's available area."""
    max_x = max(area.left(), area.left() + area.width() - geometry.width())
    max_y = max(area.top(), area.top() + area.height() - geometry.height())
    x = min(max(geometry.x(), area.left()), max_x)
    y = min(max(geometry.y(), area.top()), max_y)
    return QPoint(x, y)
