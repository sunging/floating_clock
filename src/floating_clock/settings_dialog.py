"""设置对话框：外观调节与闹钟管理。"""

from __future__ import annotations

import copy

from PySide6.QtCore import Qt, QTime
from PySide6.QtGui import QColor
from PySide6.QtWidgets import (
    QCheckBox,
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QGroupBox,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QPushButton,
    QSlider,
    QSpinBox,
    QTimeEdit,
    QVBoxLayout,
    QWidget,
)

from floating_clock.alarm import Alarm
from floating_clock.config import Config


class SettingsDialog(QDialog):
    """编辑 Config 的副本；接受后由调用方应用并保存。"""

    def __init__(self, config: Config, parent=None):
        super().__init__(parent)
        self.setWindowTitle("浮动时钟 — 设置")
        self._config = copy.deepcopy(config)
        self._selected_color = self._config.color

        layout = QVBoxLayout(self)
        layout.addWidget(self._build_appearance_group())
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
        form.addRow("字号", self._font_spin)

        self._opacity_slider = QSlider(Qt.Horizontal)
        self._opacity_slider.setRange(10, 100)
        self._opacity_slider.setValue(int(self._config.opacity * 100))
        self._opacity_label = QLabel(f"{self._opacity_slider.value()}%")
        self._opacity_slider.valueChanged.connect(
            lambda v: self._opacity_label.setText(f"{v}%")
        )
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
        form.addRow(self._seconds_chk)

        self._date_chk = QCheckBox("显示日期")
        self._date_chk.setChecked(self._config.show_date)
        form.addRow(self._date_chk)

        self._click_through_chk = QCheckBox("鼠标穿透（不影响下层窗口）")
        self._click_through_chk.setChecked(self._config.click_through)
        form.addRow(self._click_through_chk)

        return group

    def _update_color_btn(self) -> None:
        self._color_btn.setText(self._selected_color)
        self._color_btn.setStyleSheet(
            f"background-color: {self._selected_color};"
        )

    def _pick_color(self) -> None:
        color = QColorDialog.getColor(
            QColor(self._selected_color), self, "选择文字颜色"
        )
        if color.isValid():
            self._selected_color = color.name()
            self._update_color_btn()

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
        repeat = "每天" if alarm.repeat_daily else "单次"
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
        """用一个小对话框编辑时间/标签/重复，返回 Alarm 或 None。"""
        dlg = QDialog(self)
        dlg.setWindowTitle("编辑闹钟")
        form = QFormLayout(dlg)

        time_edit = QTimeEdit()
        time_edit.setDisplayFormat("HH:mm")
        h, m = _parse_hhmm(alarm.time)
        time_edit.setTime(QTime(h, m))
        form.addRow("时间", time_edit)

        label_edit = QLineEdit(alarm.label)
        form.addRow("标签", label_edit)

        repeat_chk = QCheckBox("每天重复")
        repeat_chk.setChecked(alarm.repeat_daily)
        form.addRow(repeat_chk)

        buttons = QDialogButtonBox(
            QDialogButtonBox.Ok | QDialogButtonBox.Cancel
        )
        buttons.accepted.connect(dlg.accept)
        buttons.rejected.connect(dlg.reject)
        form.addRow(buttons)

        if dlg.exec() != QDialog.Accepted:
            return None

        alarm.time = time_edit.time().toString("HH:mm")
        alarm.label = label_edit.text().strip() or "闹钟"
        alarm.repeat_daily = repeat_chk.isChecked()
        alarm.enabled = True
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
