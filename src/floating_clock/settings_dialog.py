"""设置对话框：外观调节与闹钟管理。"""

from __future__ import annotations

import copy
from typing import Callable, Optional

from PySide6.QtCore import Qt
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QDoubleSpinBox,
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
    QSlider,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from floating_clock import autostart
from floating_clock.alarm import (
    REPEAT_CUSTOM,
    REPEAT_DAILY,
    REPEAT_ONCE,
    REPEAT_WEEKDAYS,
    WEEKDAY_NAMES,
    Alarm,
)
from floating_clock.config import Config


class SettingsDialog(QDialog):
    """编辑 Config 的副本；接受后由调用方应用并保存。"""

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
        self._selected_alarm_text_color = self._config.alarm_popup_text_color
        self._selected_alarm_bg_color = self._config.alarm_popup_background_color
        self._on_preview = on_preview
        self._on_alarm_preview = on_alarm_preview

        layout = QVBoxLayout(self)

        # 顶部两列：左侧外观，右侧闹钟弹出样式，缩短整体高度并拓宽布局。
        top_row = QHBoxLayout()
        top_row.addWidget(self._build_appearance_group(), 0, Qt.AlignTop)
        top_row.addWidget(self._build_alarm_popup_group(), 0, Qt.AlignTop)
        layout.addLayout(top_row)

        layout.addWidget(self._build_alarm_group())

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

    # ---- 外观 ----
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
        self._update_color_btn()
        self._color_btn.clicked.connect(self._pick_color)
        form.addRow("文字颜色", self._color_btn)

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
        # Windows 上以注册表实际状态为准，避免与外部改动不一致。
        if autostart.is_supported():
            self._boot_chk.setChecked(autostart.is_enabled())
        else:
            self._boot_chk.setChecked(self._config.start_on_boot)
            self._boot_chk.setEnabled(False)
            self._boot_chk.setToolTip("仅 Windows 支持开机自启动")
        form.addRow(self._boot_chk)

        return group

    def _update_color_btn(self) -> None:
        _set_color_button(self._color_btn, self._selected_color)

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._selected_color), self, "选择文字颜色"
        )
        if color.isValid():
            self._selected_color = color.name()
            self._update_color_btn()
            self._emit_preview()

    # ---- 闹钟弹出样式 ----
    def _build_alarm_popup_group(self) -> QGroupBox:
        group = QGroupBox("闹钟弹出样式")
        form = QFormLayout(group)

        self._alarm_text_color_btn = QPushButton()
        _set_color_button(
            self._alarm_text_color_btn,
            self._selected_alarm_text_color,
        )
        self._alarm_text_color_btn.clicked.connect(self._pick_alarm_text_color)
        form.addRow("提醒文字颜色", self._alarm_text_color_btn)

        self._alarm_bg_color_btn = QPushButton()
        _set_color_button(self._alarm_bg_color_btn, self._selected_alarm_bg_color)
        self._alarm_bg_color_btn.clicked.connect(self._pick_alarm_bg_color)
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
        self._alarm_layout_combo.addItem("名称/内容在上，时间在下", "label_time")
        self._alarm_layout_combo.addItem("时间在上，名称/内容在下", "time_label")
        self._alarm_layout_combo.addItem("仅显示名称/内容", "label_only")
        idx = self._alarm_layout_combo.findData(
            self._config.alarm_popup_layout
        )
        self._alarm_layout_combo.setCurrentIndex(max(0, idx))
        form.addRow("布局", self._alarm_layout_combo)

        preview_btn = QPushButton("预览")
        preview_btn.clicked.connect(self._emit_alarm_preview)
        form.addRow(preview_btn)

        return group

    def _pick_alarm_text_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._selected_alarm_text_color),
            self,
            "选择提醒文字颜色",
        )
        if color.isValid():
            self._selected_alarm_text_color = color.name()
            _set_color_button(
                self._alarm_text_color_btn,
                self._selected_alarm_text_color,
            )

    def _pick_alarm_bg_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._selected_alarm_bg_color),
            self,
            "选择提醒背景颜色",
        )
        if color.isValid():
            self._selected_alarm_bg_color = color.name()
            _set_color_button(
                self._alarm_bg_color_btn,
                self._selected_alarm_bg_color,
            )

    # ---- 实时预览 ----
    def _current_preview(self) -> Config:
        """根据当前控件值构造预览配置，保留位置/穿透/闹钟等不变。"""
        cfg = copy.deepcopy(self._config)
        cfg.font_size = self._font_spin.value()
        cfg.opacity = self._opacity_slider.value() / 100.0
        cfg.color = self._selected_color
        cfg.show_seconds = self._seconds_chk.isChecked()
        cfg.show_date = self._date_chk.isChecked()
        self._apply_alarm_popup_values(cfg)
        return cfg

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

    # ---- 闹钟 ----
    def _build_alarm_group(self) -> QGroupBox:
        group = QGroupBox("闹钟")
        v = QVBoxLayout(group)

        self._alarm_list = QListWidget()
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

    def _edit_alarm_dialog(self, alarm: Alarm):
        """用一个小对话框编辑时间/名称/内容/重复，返回 Alarm 或 None。"""
        dlg = QDialog(self)
        dlg.setWindowTitle("编辑闹钟")
        form = QFormLayout(dlg)

        h, m = _parse_hhmm(alarm.time)
        hour_combo = QComboBox()
        hour_combo.addItems([f"{i:02d}" for i in range(24)])
        hour_combo.setCurrentIndex(h)
        minute_combo = QComboBox()
        minute_combo.addItems([f"{i:02d}" for i in range(60)])
        minute_combo.setCurrentIndex(m)
        # 下拉滚轮式时间选择：点击即可选小时/分钟，触控友好。
        time_row = QHBoxLayout()
        time_row.addWidget(hour_combo)
        time_row.addWidget(QLabel(":"))
        time_row.addWidget(minute_combo)
        time_row.addStretch(1)
        time_w = QWidget()
        time_w.setLayout(time_row)
        form.addRow("时间", time_w)

        label_edit = QLineEdit(alarm.label)
        form.addRow("名称", label_edit)

        content_edit = QPlainTextEdit(alarm.content)
        content_edit.setFixedHeight(72)
        form.addRow("内容", content_edit)

        repeat_combo = QComboBox()
        repeat_combo.addItem("单次", REPEAT_ONCE)
        repeat_combo.addItem("每天", REPEAT_DAILY)
        repeat_combo.addItem("工作日", REPEAT_WEEKDAYS)
        repeat_combo.addItem("自定义星期", REPEAT_CUSTOM)
        repeat_idx = repeat_combo.findData(alarm.repeat_type)
        repeat_combo.setCurrentIndex(max(0, repeat_idx))
        form.addRow("重复", repeat_combo)

        weekday_row = QHBoxLayout()
        weekday_checks: list[QCheckBox] = []
        selected_weekdays = (
            alarm.repeat_weekdays if alarm.repeat_weekdays else [0, 1, 2, 3, 4]
        )
        for index, name in enumerate(WEEKDAY_NAMES):
            chk = QCheckBox(name)
            chk.setChecked(index in selected_weekdays)
            weekday_checks.append(chk)
            weekday_row.addWidget(chk)
        weekday_w = QWidget()
        weekday_w.setLayout(weekday_row)
        form.addRow("自定义", weekday_w)

        def update_weekday_enabled() -> None:
            enabled = repeat_combo.currentData() == REPEAT_CUSTOM
            weekday_w.setEnabled(enabled)

        repeat_combo.currentIndexChanged.connect(update_weekday_enabled)
        update_weekday_enabled()

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )

        def accept_alarm() -> None:
            repeat_type = repeat_combo.currentData()
            repeat_weekdays = [
                i for i, chk in enumerate(weekday_checks) if chk.isChecked()
            ]
            if repeat_type == REPEAT_CUSTOM and not repeat_weekdays:
                QMessageBox.warning(
                    dlg,
                    "编辑闹钟",
                    "自定义重复周期至少需要选择一天。",
                )
                return
            dlg.accept()

        buttons.accepted.connect(accept_alarm)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() != QDialog.Accepted:
            return None

        alarm.time = f"{hour_combo.currentIndex():02d}:{minute_combo.currentIndex():02d}"
        alarm.label = label_edit.text().strip() or "闹钟"
        alarm.content = content_edit.toPlainText().strip()
        alarm.repeat_type = repeat_combo.currentData()
        alarm.repeat_weekdays = [
            i for i, chk in enumerate(weekday_checks) if chk.isChecked()
        ]
        alarm.enabled = True
        alarm.__post_init__()
        return alarm

    # ---- 结果 ----
    def result_config(self) -> Config:
        """从控件读取最终配置（调用方在 exec()==Accepted 后调用）。"""
        cfg = self._config
        cfg.font_size = self._font_spin.value()
        cfg.opacity = self._opacity_slider.value() / 100.0
        cfg.color = self._selected_color
        cfg.show_seconds = self._seconds_chk.isChecked()
        cfg.show_date = self._date_chk.isChecked()
        cfg.click_through = self._click_through_chk.isChecked()
        cfg.start_on_boot = self._boot_chk.isChecked()
        self._apply_alarm_popup_values(cfg)

        alarms: list[Alarm] = []
        for i in range(self._alarm_list.count()):
            item = self._alarm_list.item(i)
            alarm: Alarm = item.data(Qt.UserRole)
            alarm.enabled = item.checkState() == Qt.Checked
            alarms.append(alarm)
        cfg.alarms = alarms
        return cfg


def _parse_hhmm(value: str) -> tuple[int, int]:
    try:
        h, m = value.split(":")
        return int(h), int(m)
    except (ValueError, AttributeError):
        return 8, 0


def _set_color_button(button: QPushButton, color: str) -> None:
    """更新颜色按钮文本和色块。"""
    button.setText(color)
    button.setStyleSheet(f"background-color: {color};")


def _repeat_label(alarm: Alarm) -> str:
    """返回列表里展示的重复周期文本。"""
    if alarm.repeat_type == REPEAT_ONCE:
        return "单次"
    if alarm.repeat_type == REPEAT_DAILY:
        return "每天"
    if alarm.repeat_type == REPEAT_WEEKDAYS:
        return "工作日"
    if alarm.repeat_type == REPEAT_CUSTOM:
        names = [
            WEEKDAY_NAMES[i]
            for i in alarm.repeat_weekdays
            if 0 <= i < len(WEEKDAY_NAMES)
        ]
        return "、".join(names) if names else "自定义"
    return "每天"
