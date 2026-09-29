"""Settings dialog: appearance tuning and alarm management."""

from __future__ import annotations

import copy
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor, QGuiApplication
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMessageBox,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from floating_clock import autostart, sound
from floating_clock.alarm import (
    REPEAT_CUSTOM,
    REPEAT_DAILY,
    REPEAT_ONCE,
    REPEAT_WEEKDAYS,
    WEEKDAY_NAMES,
    WORKDAY_INDICES,
    Alarm,
)
from floating_clock.config import (
    POPUP_LAYOUT_LABEL_ONLY,
    POPUP_LAYOUT_LABEL_TIME,
    POPUP_LAYOUT_TIME_LABEL,
    Config,
)


class SettingsDialog(QDialog):
    """Edits a copy of Config; once accepted, the caller applies and saves it."""

    def __init__(
        self,
        config: Config,
        parent=None,
        on_preview: Optional[Callable[[Config], None]] = None,
        on_alarm_preview: Optional[Callable[[Config], None]] = None,
    ):
        super().__init__(parent)
        self.setWindowTitle("浮动时钟 — 设置")
        self._config = copy.deepcopy(config)
        self._selected_color = self._config.color
        self._selected_auto_dark = self._config.auto_color_dark_bg
        self._selected_auto_light = self._config.auto_color_light_bg
        self._selected_alarm_text_color = self._config.alarm_popup_text_color
        self._selected_alarm_bg_color = self._config.alarm_popup_background_color
        self._on_preview = on_preview
        self._on_alarm_preview = on_alarm_preview

        layout = QVBoxLayout(self)

        # Content is scrollable so that at high system DPI scaling factors,
        # the dialog still fits on screen instead of overflowing off the bottom.
        content = QWidget()
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(0, 0, 0, 0)

        # Top two columns: appearance on the left, alarm popup style on the right,
        # to shorten overall height and widen the layout.
        top_row = QHBoxLayout()
        top_row.addWidget(self._build_appearance_group(), 0, Qt.AlignTop)
        top_row.addWidget(self._build_alarm_popup_group(), 0, Qt.AlignTop)
        content_layout.addLayout(top_row)

        content_layout.addWidget(self._build_sound_group())
        content_layout.addWidget(self._build_alarm_group())

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QScrollArea.NoFrame)
        scroll.setWidget(content)
        layout.addWidget(scroll)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self._size_to_screen(content)

    def _size_to_screen(self, content: QWidget) -> None:
        """Cap the dialog to the available screen geometry so a high system
        DPI scale factor can't push it (or its buttons) off-screen."""
        screen = self.screen() or QGuiApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        hint = content.sizeHint()
        width = hint.width() + 40
        height = hint.height() + 80
        if available is not None:
            width = min(width, available.width() - 40)
            height = min(height, available.height() - 40)
        self.resize(width, height)

    # ---- Appearance ----
    def _build_appearance_group(self) -> QGroupBox:
        group = QGroupBox("外观")
        form = QFormLayout(group)

        self._font_spin = QSpinBox()
        self._font_spin.setRange(8, 400)
        self._font_spin.setValue(self._config.font_size)
        self._font_spin.valueChanged.connect(self._emit_preview)
        form.addRow("字号", self._font_spin)

        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(int(self._config.opacity * 100))
        self._opacity_label = QLabel(f"{self._opacity_slider.value()}%")
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
        self._opacity_slider.valueChanged.connect(self._emit_preview)
        opacity_row = QHBoxLayout()
        opacity_row.addWidget(self._opacity_slider)
        opacity_row.addWidget(self._opacity_label)
        opacity_w = QWidget()
        opacity_w.setLayout(opacity_row)
        form.addRow("透明度", opacity_w)

        self._color_btn = QPushButton()
        _set_color_button(self._color_btn, self._selected_color)
        self._color_btn.clicked.connect(
            lambda: self._pick_color("_selected_color", self._color_btn, "选择文字颜色")
        )
        form.addRow("文字颜色", self._color_btn)

        self._auto_color_chk = QCheckBox("自动适配背景色")
        self._auto_color_chk.setChecked(self._config.auto_color)
        form.addRow(self._auto_color_chk)

        self._auto_dark_btn = QPushButton()
        _set_color_button(self._auto_dark_btn, self._selected_auto_dark)
        self._auto_dark_btn.clicked.connect(
            lambda: self._pick_color(
                "_selected_auto_dark", self._auto_dark_btn, "选择深色背景下的文字颜色"
            )
        )
        form.addRow("深色背景用色", self._auto_dark_btn)

        self._auto_light_btn = QPushButton()
        _set_color_button(self._auto_light_btn, self._selected_auto_light)
        self._auto_light_btn.clicked.connect(
            lambda: self._pick_color(
                "_selected_auto_light", self._auto_light_btn, "选择浅色背景下的文字颜色"
            )
        )
        form.addRow("浅色背景用色", self._auto_light_btn)

        # Initialize each button's enabled state (manual color is overridden in auto mode).
        self._update_auto_color_enabled()
        # Connect the signal after building, so init doesn't trigger a preview before widgets are ready.
        self._auto_color_chk.toggled.connect(self._on_auto_color_toggled)

        self._seconds_chk = QCheckBox("显示秒")
        self._seconds_chk.setChecked(self._config.show_seconds)
        self._seconds_chk.toggled.connect(self._emit_preview)
        form.addRow(self._seconds_chk)

        self._date_chk = QCheckBox("显示日期")
        self._date_chk.setChecked(self._config.show_date)
        self._date_chk.toggled.connect(self._emit_preview)
        form.addRow(self._date_chk)

        self._click_through_chk = QCheckBox("鼠标穿透（不影响下层窗口）")
        self._click_through_chk.setChecked(self._config.click_through)
        form.addRow(self._click_through_chk)

        self._boot_chk = QCheckBox("开机自启动")
        # On Windows, trust the registry's actual state to avoid drift from external changes.
        if autostart.is_supported():
            self._boot_chk.setChecked(autostart.is_enabled())
        else:
            self._boot_chk.setChecked(self._config.start_on_boot)
            self._boot_chk.setEnabled(False)
            self._boot_chk.setToolTip("仅 Windows 支持开机自启动")
        form.addRow(self._boot_chk)

        return group

    def _pick_color(
        self, attr: str, button: QPushButton, title: str, preview: bool = True
    ) -> None:
        """Let the user pick a color into ``self.<attr>`` and refresh its swatch button.

        ``preview`` pushes the change to the live clock; alarm popup colors
        only show up through the explicit "preview" button, so they pass False.
        """
        color = QColorDialog.getColor(QColor(getattr(self, attr)), self, title)
        if not color.isValid():
            return
        setattr(self, attr, color.name())
        _set_color_button(button, color.name())
        if preview:
            self._emit_preview()

    def _on_auto_color_toggled(self, _checked: bool) -> None:
        self._update_auto_color_enabled()
        self._emit_preview()

    def _update_auto_color_enabled(self) -> None:
        """In auto mode, disable the manual text color and enable the light/dark background color buttons."""
        auto = self._auto_color_chk.isChecked()
        self._color_btn.setEnabled(not auto)
        self._auto_dark_btn.setEnabled(auto)
        self._auto_light_btn.setEnabled(auto)

    # ---- Alarm popup style ----
    def _build_alarm_popup_group(self) -> QGroupBox:
        group = QGroupBox("闹钟弹出样式")
        form = QFormLayout(group)

        self._alarm_text_color_btn = QPushButton()
        _set_color_button(
            self._alarm_text_color_btn,
            self._selected_alarm_text_color,
        )
        self._alarm_text_color_btn.clicked.connect(
            lambda: self._pick_color(
                "_selected_alarm_text_color",
                self._alarm_text_color_btn,
                "选择提醒文字颜色",
                preview=False,
            )
        )
        form.addRow("提醒文字颜色", self._alarm_text_color_btn)

        self._alarm_bg_color_btn = QPushButton()
        _set_color_button(self._alarm_bg_color_btn, self._selected_alarm_bg_color)
        self._alarm_bg_color_btn.clicked.connect(
            lambda: self._pick_color(
                "_selected_alarm_bg_color",
                self._alarm_bg_color_btn,
                "选择提醒背景颜色",
                preview=False,
            )
        )
        form.addRow("背景颜色", self._alarm_bg_color_btn)

        self._alarm_bg_opacity_slider = QSlider(Qt.Horizontal)
        self._alarm_bg_opacity_slider.setRange(0, 100)
        self._alarm_bg_opacity_slider.setValue(
            int(self._config.alarm_popup_background_opacity * 100)
        )
        self._alarm_bg_opacity_label = QLabel(
            f"{self._alarm_bg_opacity_slider.value()}%"
        )
        self._alarm_bg_opacity_slider.valueChanged.connect(
            lambda v: self._alarm_bg_opacity_label.setText(f"{v}%")
        )
        bg_opacity_row = QHBoxLayout()
        bg_opacity_row.addWidget(self._alarm_bg_opacity_slider)
        bg_opacity_row.addWidget(self._alarm_bg_opacity_label)
        bg_opacity_w = QWidget()
        bg_opacity_w.setLayout(bg_opacity_row)
        form.addRow("背景透明度", bg_opacity_w)

        self._alarm_flash_chk = QCheckBox("启用闪烁")
        self._alarm_flash_chk.setChecked(
            self._config.alarm_popup_flash_enabled
        )
        form.addRow(self._alarm_flash_chk)

        self._alarm_font_scale_spin = QDoubleSpinBox()
        self._alarm_font_scale_spin.setRange(0.5, 3.0)
        self._alarm_font_scale_spin.setSingleStep(0.1)
        self._alarm_font_scale_spin.setDecimals(1)
        self._alarm_font_scale_spin.setValue(
            self._config.alarm_popup_font_scale
        )
        form.addRow("字号倍率", self._alarm_font_scale_spin)

        self._alarm_layout_combo = QComboBox()
        self._alarm_layout_combo.addItem("名称/内容在上，时间在下", POPUP_LAYOUT_LABEL_TIME)
        self._alarm_layout_combo.addItem("时间在上，名称/内容在下", POPUP_LAYOUT_TIME_LABEL)
        self._alarm_layout_combo.addItem("仅显示名称/内容", POPUP_LAYOUT_LABEL_ONLY)
        idx = self._alarm_layout_combo.findData(
            self._config.alarm_popup_layout
        )
        self._alarm_layout_combo.setCurrentIndex(max(0, idx))
        form.addRow("布局", self._alarm_layout_combo)

        preview_btn = QPushButton("预览")
        preview_btn.clicked.connect(self._emit_alarm_preview)
        form.addRow(preview_btn)

        return group

    # ---- Live preview ----
    def _current_preview(self) -> Config:
        """Build a preview config from current widget values, leaving position/click-through/alarms unchanged."""
        cfg = copy.deepcopy(self._config)
        self._apply_appearance_values(cfg)
        self._apply_alarm_popup_values(cfg)
        return cfg

    def _apply_appearance_values(self, cfg: Config) -> None:
        cfg.font_size = self._font_spin.value()
        cfg.opacity = self._opacity_slider.value() / 100.0
        cfg.color = self._selected_color
        cfg.auto_color = self._auto_color_chk.isChecked()
        cfg.auto_color_dark_bg = self._selected_auto_dark
        cfg.auto_color_light_bg = self._selected_auto_light
        cfg.show_seconds = self._seconds_chk.isChecked()
        cfg.show_date = self._date_chk.isChecked()

    def _emit_preview(self) -> None:
        if self._on_preview is not None:
            self._on_preview(self._current_preview())

    def _emit_alarm_preview(self) -> None:
        if self._on_alarm_preview is not None:
            self._on_alarm_preview(self._current_preview())

    def _apply_alarm_popup_values(self, cfg: Config) -> None:
        cfg.alarm_popup_text_color = self._selected_alarm_text_color
        cfg.alarm_popup_background_color = self._selected_alarm_bg_color
        cfg.alarm_popup_background_opacity = (
            self._alarm_bg_opacity_slider.value() / 100.0
        )
        cfg.alarm_popup_flash_enabled = self._alarm_flash_chk.isChecked()
        cfg.alarm_popup_font_scale = self._alarm_font_scale_spin.value()
        cfg.alarm_popup_layout = self._alarm_layout_combo.currentData()

    # ---- Sound ----
    def _build_sound_group(self) -> QGroupBox:
        group = QGroupBox("提示音与响铃")
        form = QFormLayout(group)

        self._sound_mode_combo = QComboBox()
        self._sound_mode_combo.addItem("无声", sound.SOUND_SILENT)
        self._sound_mode_combo.addItem("系统提示音", sound.SOUND_SYSTEM)
        self._sound_mode_combo.addItem("自定义文件", sound.SOUND_CUSTOM)
        mode_idx = self._sound_mode_combo.findData(
            sound.normalize_mode(self._config.sound_mode)
        )
        self._sound_mode_combo.setCurrentIndex(max(0, mode_idx))
        self._sound_mode_combo.currentIndexChanged.connect(
            self._update_sound_enabled
        )
        form.addRow("提示音", self._sound_mode_combo)

        self._sound_alias_combo = QComboBox()
        for alias, name in sound.SYSTEM_SOUNDS:
            self._sound_alias_combo.addItem(name, alias)
        alias_idx = self._sound_alias_combo.findData(
            self._config.sound_system_alias
        )
        self._sound_alias_combo.setCurrentIndex(max(0, alias_idx))
        form.addRow("系统提示音", self._sound_alias_combo)

        self._sound_path_edit = QLineEdit(self._config.sound_custom_path)
        self._sound_path_edit.setPlaceholderText("选择 WAV 文件…")
        browse_btn = QPushButton("浏览…")
        browse_btn.clicked.connect(self._pick_sound_file)
        path_row = QHBoxLayout()
        path_row.addWidget(self._sound_path_edit, 1)
        path_row.addWidget(browse_btn)
        path_w = QWidget()
        path_w.setLayout(path_row)
        form.addRow("自定义文件", path_w)

        self._sound_test_btn = QPushButton("试听")
        self._sound_test_btn.clicked.connect(self._test_sound)
        form.addRow(self._sound_test_btn)

        self._ring_screen_off_chk = QCheckBox(
            "屏幕关闭时仍响铃（默认关闭，即关屏不响）"
        )
        self._ring_screen_off_chk.setChecked(self._config.ring_when_screen_off)
        form.addRow(self._ring_screen_off_chk)

        self._update_sound_enabled()
        return group

    def _update_sound_enabled(self) -> None:
        """Enable/disable the alias combo, custom file, and test button per sound mode."""
        mode = self._sound_mode_combo.currentData()
        self._sound_alias_combo.setEnabled(mode == sound.SOUND_SYSTEM)
        self._sound_path_edit.setEnabled(mode == sound.SOUND_CUSTOM)
        self._sound_test_btn.setEnabled(mode != sound.SOUND_SILENT)

    def _pick_sound_file(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "选择提示音文件",
            self._sound_path_edit.text().strip(),
            "WAV 音频 (*.wav)",
        )
        if path:
            self._sound_path_edit.setText(path)

    def _test_sound(self) -> None:
        """Preview the currently selected sound (play once, no loop)."""
        sound.play(
            self._sound_mode_combo.currentData(),
            self._sound_alias_combo.currentData(),
            self._sound_path_edit.text().strip(),
            loop=False,
        )

    def _apply_sound_values(self, cfg: Config) -> None:
        cfg.sound_mode = self._sound_mode_combo.currentData()
        cfg.sound_system_alias = self._sound_alias_combo.currentData()
        cfg.sound_custom_path = self._sound_path_edit.text().strip()
        cfg.ring_when_screen_off = self._ring_screen_off_chk.isChecked()

    # ---- Alarms ----
    def _build_alarm_group(self) -> QGroupBox:
        group = QGroupBox("闹钟")
        v = QVBoxLayout(group)

        self._alarm_list = QListWidget()
        # Double-click a row to edit directly, skipping the "select + click Edit" two steps.
        self._alarm_list.itemDoubleClicked.connect(
            lambda _item: self._edit_alarm()
        )
        for alarm in self._config.alarms:
            self._add_alarm_item(alarm)
        v.addWidget(self._alarm_list)

        btn_row = QHBoxLayout()
        add_btn = QPushButton("新增")
        edit_btn = QPushButton("编辑")
        del_btn = QPushButton("删除")
        add_btn.clicked.connect(self._add_alarm)
        edit_btn.clicked.connect(self._edit_alarm)
        del_btn.clicked.connect(self._del_alarm)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(edit_btn)
        btn_row.addWidget(del_btn)
        v.addLayout(btn_row)
        return group

    def _add_alarm_item(self, alarm: Alarm) -> None:
        item = QListWidgetItem(self._alarm_text(alarm))
        item.setData(Qt.UserRole, alarm)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked if alarm.enabled else Qt.Unchecked)
        self._alarm_list.addItem(item)

    @staticmethod
    def _alarm_text(alarm: Alarm) -> str:
        repeat = _repeat_label(alarm)
        return f"{alarm.time}  {alarm.label}  [{repeat}]"

    def _add_alarm(self) -> None:
        alarm = self._edit_alarm_dialog(Alarm())
        if alarm is not None:
            self._add_alarm_item(alarm)

    def _edit_alarm(self) -> None:
        item = self._alarm_list.currentItem()
        if item is None:
            return
        alarm: Alarm = item.data(Qt.UserRole)
        updated = self._edit_alarm_dialog(copy.deepcopy(alarm))
        if updated is not None:
            updated.enabled = item.checkState() == Qt.Checked
            item.setData(Qt.UserRole, updated)
            item.setText(self._alarm_text(updated))

    def _del_alarm(self) -> None:
        row = self._alarm_list.currentRow()
        if row >= 0:
            self._alarm_list.takeItem(row)

    def _edit_alarm_dialog(self, alarm: Alarm) -> Optional[Alarm]:
        """Edit an alarm in a modal sub-dialog; return it updated, or None if cancelled."""
        dlg = AlarmEditDialog(alarm, self)
        try:
            if dlg.exec() != QDialog.Accepted:
                return None
            return dlg.alarm()
        finally:
            dlg.deleteLater()

    # ---- Result ----
    def mark_alarm_fired(self, fired: Alarm) -> None:
        """Consume a one-shot in the editor unless its schedule was changed."""
        for index in range(self._alarm_list.count()):
            item = self._alarm_list.item(index)
            alarm: Alarm = item.data(Qt.UserRole)
            if alarm.id != fired.id:
                continue
            if (alarm.time, alarm.repeat_type, alarm.repeat_weekdays) == (
                fired.time, fired.repeat_type, fired.repeat_weekdays
            ):
                alarm.enabled = False
                item.setData(Qt.UserRole, alarm)
                item.setCheckState(Qt.Unchecked)
            break

    def result_config(self) -> Config:
        """Read the final config from the widgets (called after exec()==Accepted)."""
        cfg = self._config
        self._apply_appearance_values(cfg)
        cfg.click_through = self._click_through_chk.isChecked()
        cfg.start_on_boot = self._boot_chk.isChecked()
        self._apply_alarm_popup_values(cfg)
        self._apply_sound_values(cfg)

        alarms: list[Alarm] = []
        for i in range(self._alarm_list.count()):
            item = self._alarm_list.item(i)
            alarm: Alarm = item.data(Qt.UserRole)
            alarm.enabled = item.checkState() == Qt.Checked
            alarms.append(alarm)
        cfg.alarms = alarms
        return cfg


class AlarmEditDialog(QDialog):
    """Edits one alarm's time, name, content, and repeat rule."""

    def __init__(self, alarm: Alarm, parent=None):
        super().__init__(parent)
        self._alarm = alarm
        self.setWindowTitle("编辑闹钟")
        form = QFormLayout(self)

        # Dropdown-style time picking: click to choose hour/minute, touch-friendly.
        h, m = _parse_hhmm(alarm.time)
        self._hour_combo = QComboBox()
        self._hour_combo.addItems([f"{i:02d}" for i in range(24)])
        self._hour_combo.setCurrentIndex(h)
        self._minute_combo = QComboBox()
        self._minute_combo.addItems([f"{i:02d}" for i in range(60)])
        self._minute_combo.setCurrentIndex(m)
        time_row = QHBoxLayout()
        time_row.addWidget(self._hour_combo)
        time_row.addWidget(QLabel(":"))
        time_row.addWidget(self._minute_combo)
        time_row.addStretch(1)
        time_w = QWidget()
        time_w.setLayout(time_row)
        form.addRow("时间", time_w)

        self._label_edit = QLineEdit(alarm.label)
        form.addRow("名称", self._label_edit)

        self._content_edit = QPlainTextEdit(alarm.content)
        self._content_edit.setFixedHeight(72)
        form.addRow("内容", self._content_edit)

        self._repeat_combo = QComboBox()
        for repeat_type, name in _REPEAT_NAMES.items():
            self._repeat_combo.addItem(name, repeat_type)
        self._repeat_combo.setCurrentIndex(
            max(0, self._repeat_combo.findData(alarm.repeat_type))
        )
        form.addRow("重复", self._repeat_combo)

        weekday_row = QHBoxLayout()
        self._weekday_checks: list[QCheckBox] = []
        # Pre-select workdays so switching to "custom" starts from a sensible set.
        selected = alarm.repeat_weekdays or WORKDAY_INDICES
        for index, name in enumerate(WEEKDAY_NAMES):
            chk = QCheckBox(name)
            chk.setChecked(index in selected)
            self._weekday_checks.append(chk)
            weekday_row.addWidget(chk)
        self._weekday_w = QWidget()
        self._weekday_w.setLayout(weekday_row)
        form.addRow("自定义", self._weekday_w)

        self._repeat_combo.currentIndexChanged.connect(self._update_weekday_enabled)
        self._update_weekday_enabled()

        buttons = QDialogButtonBox(QDialogButtonBox.Ok | QDialogButtonBox.Cancel)
        buttons.accepted.connect(self._validate_and_accept)
        buttons.rejected.connect(self.reject)
        form.addRow(buttons)

    def _selected_weekdays(self) -> list[int]:
        return [i for i, chk in enumerate(self._weekday_checks) if chk.isChecked()]

    def _update_weekday_enabled(self) -> None:
        self._weekday_w.setEnabled(self._repeat_combo.currentData() == REPEAT_CUSTOM)

    def _validate_and_accept(self) -> None:
        if self._repeat_combo.currentData() == REPEAT_CUSTOM and not self._selected_weekdays():
            QMessageBox.warning(self, "编辑闹钟", "自定义重复周期至少需要选择一天。")
            return
        self.accept()

    def alarm(self) -> Alarm:
        """Write the edited values into the alarm passed in (enabled) and return it."""
        alarm = self._alarm
        alarm.time = f"{self._hour_combo.currentIndex():02d}:{self._minute_combo.currentIndex():02d}"
        alarm.label = self._label_edit.text().strip() or "闹钟"
        alarm.content = self._content_edit.toPlainText().strip()
        alarm.repeat_type = self._repeat_combo.currentData()
        alarm.repeat_weekdays = self._selected_weekdays()
        alarm.enabled = True
        alarm.normalize()
        return alarm


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        h, m = value.split(":")
        return int(h), int(m)
    except (ValueError, AttributeError):
        return 8, 0


def _set_color_button(button: QPushButton, color: str) -> None:
    """Update the color button's text and swatch."""
    button.setText(color)
    button.setStyleSheet(f"background-color: {color};")


# Repeat-rule names, in the order offered by the alarm editor.
_REPEAT_NAMES = {
    REPEAT_ONCE: "单次",
    REPEAT_DAILY: "每天",
    REPEAT_WEEKDAYS: "工作日",
    REPEAT_CUSTOM: "自定义星期",
}


def _repeat_label(alarm: Alarm) -> str:
    """Return the repeat-period text shown in the list."""
    if alarm.repeat_type == REPEAT_CUSTOM:
        names = [WEEKDAY_NAMES[i] for i in alarm.repeat_weekdays]
        return "、".join(names) if names else "自定义"
    return _REPEAT_NAMES.get(alarm.repeat_type, _REPEAT_NAMES[REPEAT_DAILY])
