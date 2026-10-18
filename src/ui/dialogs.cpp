#include "ui/dialogs.h"
#include "version.h"

#include <QCloseEvent>
#include <QColorDialog>
#include <QCoreApplication>
#include <QDialogButtonBox>
#include <QDoubleSpinBox>
#include <QFile>
#include <QFileDialog>
#include <QFormLayout>
#include <QGroupBox>
#include <QHBoxLayout>
#include <QMessageBox>
#include <QSaveFile>
#include <QScreen>
#include <QScrollArea>
#include <QSignalBlocker>
#include <QTabWidget>
#include <QVBoxLayout>
#include <algorithm>
#include <functional>

namespace fc {
namespace {
const QStringList DayNames{QStringLiteral("周一"), QStringLiteral("周二"), QStringLiteral("周三"),
                           QStringLiteral("周四"), QStringLiteral("周五"), QStringLiteral("周六"),
                           QStringLiteral("周日")};

QString repeatName(const Alarm &alarm) {
    if (alarm.repeat == "once")
        return QStringLiteral("单次");
    if (alarm.repeat == "weekdays")
        return QStringLiteral("工作日");
    if (alarm.repeat == "custom") {
        QStringList days;
        for (int day : alarm.weekdays)
            days.append(DayNames.at(day));
        return days.join(' ');
    }
    return QStringLiteral("每天");
}

QWidget *scrollPage(QFormLayout **form) {
    auto *content = new QWidget;
    *form = new QFormLayout(content);
    (*form)->setFieldGrowthPolicy(QFormLayout::AllNonFixedFieldsGrow);
    auto *scroll = new QScrollArea;
    scroll->setWidgetResizable(true);
    scroll->setWidget(content);
    scroll->setFrameShape(QFrame::NoFrame);
    return scroll;
}

QSpinBox *integer(QFormLayout *form, const QString &label, int &value, int low, int high,
                  const std::function<void()> &changed = {}) {
    auto *spin = new QSpinBox;
    spin->setRange(low, high);
    spin->setValue(value);
    QObject::connect(spin, &QSpinBox::valueChanged, spin, [&value, changed](int input) {
        value = input;
        if (changed)
            changed();
    });
    form->addRow(label, spin);
    return spin;
}

void real(QFormLayout *form, const QString &label, double &value, double low, double high,
          const std::function<void()> &changed = {}) {
    auto *spin = new QDoubleSpinBox;
    spin->setRange(low, high);
    spin->setSingleStep(0.05);
    spin->setValue(value);
    QObject::connect(spin, &QDoubleSpinBox::valueChanged, spin, [&value, changed](double input) {
        value = input;
        if (changed)
            changed();
    });
    form->addRow(label, spin);
}

QCheckBox *boolean(QFormLayout *form, const QString &label, bool &value,
                   const std::function<void()> &changed = {}) {
    auto *check = new QCheckBox(label);
    check->setChecked(value);
    QObject::connect(check, &QCheckBox::toggled, check, [&value, changed](bool input) {
        value = input;
        if (changed)
            changed();
    });
    form->addRow(check);
    return check;
}

void color(QFormLayout *form, const QString &label, QString &value,
           const std::function<void()> &changed) {
    auto *button = new QPushButton(value);
    auto style = [button, &value] {
        const QColor color(value);
        button->setText(value);
        button->setStyleSheet(QStringLiteral("background: %1; color: %2;")
                                  .arg(value, color.lightness() > 128 ? "black" : "white"));
    };
    style();
    QObject::connect(button, &QPushButton::clicked, button,
                     [button, &value, changed, style, label] {
                         const QColor selected = QColorDialog::getColor(
                             QColor(value), button, label, QColorDialog::DontUseNativeDialog);
                         if (!selected.isValid())
                             return;
                         value = selected.name();
                         style();
                         changed();
                     });
    form->addRow(label, button);
}

QComboBox *choice(QFormLayout *form, const QString &label, QString &value,
                  const QList<QPair<QString, QString>> &options,
                  const std::function<void()> &changed = {}) {
    auto *combo = new QComboBox;
    for (const auto &option : options)
        combo->addItem(option.first, option.second);
    combo->setCurrentIndex(std::max(0, combo->findData(value)));
    QObject::connect(combo, &QComboBox::currentIndexChanged, combo, [&value, combo, changed] {
        value = combo->currentData().toString();
        if (changed)
            changed();
    });
    form->addRow(label, combo);
    return combo;
}

QPushButton *button(QHBoxLayout *row, const QString &label, const std::function<void()> &action) {
    auto *result = new QPushButton(label);
    QObject::connect(result, &QPushButton::clicked, result, action);
    row->addWidget(result);
    return result;
}
} // namespace

AlarmEditDialog::AlarmEditDialog(const Alarm &alarm, QWidget *parent)
    : QDialog(parent), original_(alarm) {
    setWindowTitle(QStringLiteral("编辑闹钟"));
    auto *outer = new QVBoxLayout(this);
    auto *body = new QWidget;
    auto *layout = new QVBoxLayout(body);
    auto *form = new QFormLayout;
    layout->addLayout(form);
    time_ = new QTimeEdit(QTime::fromString(alarm.time, "HH:mm"));
    time_->setObjectName("alarmTime");
    time_->setDisplayFormat("HH:mm");
    form->addRow(QStringLiteral("时间"), time_);
    label_ = new QLineEdit(alarm.label);
    label_->setObjectName("alarmLabel");
    form->addRow(QStringLiteral("名称"), label_);
    content_ = new QPlainTextEdit(alarm.content);
    content_->setObjectName("alarmContent");
    content_->setMinimumHeight(100);
    form->addRow(QStringLiteral("内容"), content_);
    repeat_ = new QComboBox;
    repeat_->setObjectName("alarmRepeat");
    repeat_->addItem(QStringLiteral("单次"), "once");
    repeat_->addItem(QStringLiteral("每天"), "daily");
    repeat_->addItem(QStringLiteral("工作日"), "weekdays");
    repeat_->addItem(QStringLiteral("自定义星期"), "custom");
    repeat_->setCurrentIndex(repeat_->findData(alarm.repeat));
    form->addRow(QStringLiteral("重复"), repeat_);
    auto *days = new QHBoxLayout;
    for (int day = 0; day < 7; ++day) {
        auto *check = new QCheckBox(DayNames.at(day));
        check->setChecked(alarm.weekdays.contains(day));
        check->setEnabled(alarm.repeat == "custom");
        days_.append(check);
        days->addWidget(check);
    }
    layout->addLayout(days);
    connect(repeat_, &QComboBox::currentIndexChanged, this, [this] {
        for (auto *day : days_)
            day->setEnabled(repeat_->currentData() == "custom");
    });
    inherit_ = new QCheckBox(QStringLiteral("使用全局提醒超时"));
    inherit_->setObjectName("inheritTimeout");
    inherit_->setChecked(!alarm.timeoutSeconds);
    form->addRow(inherit_);
    timeout_ = new QSpinBox;
    timeout_->setObjectName("alarmTimeout");
    timeout_->setRange(1, 3600);
    timeout_->setSuffix(QStringLiteral(" 秒"));
    timeout_->setValue(alarm.timeoutSeconds.value_or(60));
    timeout_->setEnabled(alarm.timeoutSeconds.has_value());
    form->addRow(QStringLiteral("自动停止"), timeout_);
    connect(inherit_, &QCheckBox::toggled, timeout_,
            [this](bool checked) { timeout_->setEnabled(!checked); });
    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
    buttons->button(QDialogButtonBox::Ok)->setText(QStringLiteral("确定"));
    buttons->button(QDialogButtonBox::Cancel)->setText(QStringLiteral("取消"));
    connect(buttons, &QDialogButtonBox::accepted, this, &AlarmEditDialog::accept);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
    auto *scroll = new QScrollArea;
    scroll->setWidgetResizable(true);
    scroll->setFrameShape(QFrame::NoFrame);
    scroll->setWidget(body);
    outer->addWidget(scroll, 1);
    outer->addWidget(buttons);
    resize(QSize(540, 440).boundedTo(screen()->availableGeometry().size() - QSize(40, 40)));
}

Alarm AlarmEditDialog::resultAlarm() const {
    Alarm result = original_;
    result.time = time_->time().toString("HH:mm");
    result.label = label_->text().trimmed();
    if (result.label.isEmpty())
        result.label = QStringLiteral("闹钟");
    result.content = content_->toPlainText();
    result.repeat = repeat_->currentData().toString();
    result.weekdays.clear();
    for (int day = 0; day < days_.size(); ++day)
        if (days_.at(day)->isChecked())
            result.weekdays.append(day);
    result.timeoutSeconds =
        inherit_->isChecked() ? std::nullopt : std::optional<int>(timeout_->value());
    result.normalize();
    return result;
}

void AlarmEditDialog::accept() {
    const auto alarm = resultAlarm();
    if (alarm.repeat == "custom" && alarm.weekdays.isEmpty()) {
        QMessageBox::warning(this, QStringLiteral("闹钟"), QStringLiteral("请至少选择一个星期。"));
        return;
    }
    QDialog::accept();
}

void AlarmEditDialog::markAlarmFired(const Alarm &fired) {
    const auto edited = resultAlarm();
    if (edited.id == fired.id && edited.time == fired.time && edited.repeat == fired.repeat &&
        edited.weekdays == fired.weekdays)
        original_.enabled = false;
}

SettingsDialog::SettingsDialog(const Config &config, const Capabilities &capabilities,
                               QWidget *parent)
    : QDialog(parent), draft_(config) {
    setWindowTitle(QStringLiteral("浮动时钟 — 设置"));
    auto *layout = new QVBoxLayout(this);
    auto *tabs = new QTabWidget;
    layout->addWidget(tabs, 1);
    const auto preview = [this] { emit previewRequested(draft_); };
    QFormLayout *form;
    tabs->addTab(scrollPage(&form), QStringLiteral("外观"));
    integer(form, QStringLiteral("字号"), draft_.fontSize, 8, 400, preview)
        ->setObjectName("fontSize");
    real(form, QStringLiteral("整体透明度"), draft_.opacity, 0.1, 1.0, preview);
    color(form, QStringLiteral("文字颜色"), draft_.color, preview);
    auto *autoColor = boolean(form, QStringLiteral("自动适配背景色"), draft_.autoColor, preview);
    autoColor->setEnabled(capabilities.screenSampling);
    color(form, QStringLiteral("深色背景用色"), draft_.darkBackgroundColor, preview);
    color(form, QStringLiteral("浅色背景用色"), draft_.lightBackgroundColor, preview);
    boolean(form, QStringLiteral("显示秒"), draft_.showSeconds, preview);
    boolean(form, QStringLiteral("显示日期"), draft_.showDate, preview);
    boolean(form, QStringLiteral("鼠标穿透"), draft_.clickThrough)
        ->setEnabled(capabilities.clickThrough);
    boolean(form, QStringLiteral("登录时自启动"), draft_.startOnBoot);
    if (!capabilities.explanation.isEmpty()) {
        auto *notice = new QLabel(capabilities.explanation);
        notice->setWordWrap(true);
        form->addRow(notice);
    }

    tabs->addTab(scrollPage(&form), QStringLiteral("提醒样式"));
    color(form, QStringLiteral("文字颜色"), draft_.popupTextColor, preview);
    color(form, QStringLiteral("背景颜色"), draft_.popupBackgroundColor, preview);
    real(form, QStringLiteral("背景透明度"), draft_.popupOpacity, 0.0, 1.0, preview);
    real(form, QStringLiteral("字号倍率"), draft_.popupFontScale, 0.5, 3.0, preview);
    boolean(form, QStringLiteral("闪烁"), draft_.popupFlash, preview);
    choice(form, QStringLiteral("布局"), draft_.popupLayout,
           {{QStringLiteral("名称/内容在上"), "label_time"},
            {QStringLiteral("时间在上"), "time_label"},
            {QStringLiteral("仅名称/内容"), "label_only"}},
           preview);
    auto *popupPreview = new QPushButton(QStringLiteral("预览提醒（3 秒）"));
    connect(popupPreview, &QPushButton::clicked, this,
            [this] { emit reminderPreviewRequested(draft_); });
    form->addRow(popupPreview);

    tabs->addTab(scrollPage(&form), QStringLiteral("声音与超时"));
    choice(form, QStringLiteral("声音"), draft_.soundMode,
           {{QStringLiteral("无声"), "silent"},
            {QStringLiteral("系统/内置提示音"), "system"},
            {QStringLiteral("自定义 WAV"), "custom"}});
#ifdef Q_OS_WIN
    choice(form, QStringLiteral("系统提示音"), draft_.soundAlias,
           {{QStringLiteral("错误"), "SystemHand"},
            {QStringLiteral("星号"), "SystemAsterisk"},
            {QStringLiteral("感叹"), "SystemExclamation"},
            {QStringLiteral("问题"), "SystemQuestion"},
            {QStringLiteral("默认"), "SystemDefault"},
            {QStringLiteral("Windows 启动"), "SystemStart"},
            {QStringLiteral("Windows 退出"), "SystemExit"}});
#endif
    auto *soundPath = new QLineEdit(draft_.soundPath);
    connect(soundPath, &QLineEdit::textChanged, this,
            [this](const QString &path) { draft_.soundPath = path; });
    form->addRow(QStringLiteral("WAV 文件"), soundPath);
    auto *browse = new QPushButton(QStringLiteral("浏览…"));
    connect(browse, &QPushButton::clicked, this, [this, soundPath] {
        // Native Windows file dialogs can block Qt timers, including reminder expiration.
        const auto path = QFileDialog::getOpenFileName(
            this, QStringLiteral("选择提示音"), draft_.soundPath,
            QStringLiteral("WAV 音频 (*.wav)"), nullptr, QFileDialog::DontUseNativeDialog);
        if (!path.isEmpty())
            soundPath->setText(path);
    });
    form->addRow(browse);
    auto *soundPreview = new QPushButton(QStringLiteral("试听（最多 3 秒）"));
    connect(soundPreview, &QPushButton::clicked, this,
            [this] { emit soundPreviewRequested(draft_); });
    form->addRow(soundPreview);
    integer(form, QStringLiteral("默认自动停止（秒）"), draft_.alarmTimeoutSeconds, 1, 3600)
        ->setObjectName("defaultTimeout");
    boolean(form, QStringLiteral("屏幕关闭时仍提醒"), draft_.ringWhenScreenOff);
    auto *power =
        new QLabel(capabilities.displayPower
                       ? QStringLiteral("默认关屏不响，且不消耗单次闹钟。")
                       : QStringLiteral("当前系统无法检测关屏，未知状态按屏幕开启处理。"));
    power->setWordWrap(true);
    form->addRow(power);

    auto *alarmPage = new QWidget;
    auto *alarmLayout = new QVBoxLayout(alarmPage);
    alarms_ = new QListWidget;
    alarms_->setObjectName("alarmList");
    alarms_->setWordWrap(true);
    alarmLayout->addWidget(alarms_, 1);
    auto *row = new QHBoxLayout;
    button(row, QStringLiteral("新增"), [this] { editAlarm(true); });
    button(row, QStringLiteral("编辑"), [this] { editAlarm(false); });
    button(row, QStringLiteral("删除"), [this] {
        const int row = alarms_->currentRow();
        if (row >= 0) {
            draft_.alarms.removeAt(row);
            refreshAlarms();
        }
    });
    alarmLayout->addLayout(row);
    connect(alarms_, &QListWidget::itemDoubleClicked, this, [this] { editAlarm(false); });
    connect(alarms_, &QListWidget::itemChanged, this, [this](QListWidgetItem *item) {
        const int row = alarms_->row(item);
        if (row >= 0 && row < draft_.alarms.size())
            draft_.alarms[row].enabled = item->checkState() == Qt::Checked;
    });
    refreshAlarms();
    tabs->addTab(alarmPage, QStringLiteral("闹钟"));
    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
    buttons->button(QDialogButtonBox::Ok)->setText(QStringLiteral("确定"));
    buttons->button(QDialogButtonBox::Cancel)->setText(QStringLiteral("取消"));
    connect(buttons, &QDialogButtonBox::accepted, this, &QDialog::accept);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
    layout->addWidget(buttons);
    const QSize available = screen()->availableGeometry().size() - QSize(40, 40);
    resize(QSize(640, 650).boundedTo(available));
}

Config SettingsDialog::resultConfig() const {
    return draft_;
}

void SettingsDialog::refreshAlarms() {
    const QSignalBlocker block(alarms_);
    const int selection = alarms_->currentRow();
    alarms_->clear();
    for (const auto &alarm : draft_.alarms) {
        const QString timeout = alarm.timeoutSeconds
                                    ? QStringLiteral("%1 秒后停止").arg(*alarm.timeoutSeconds)
                                    : QStringLiteral("全局超时");
        auto *item =
            new QListWidgetItem(QStringLiteral("%1  %2 · %3 · %4")
                                    .arg(alarm.time, alarm.label, repeatName(alarm), timeout));
        item->setData(Qt::UserRole, alarm.id);
        item->setFlags(item->flags() | Qt::ItemIsUserCheckable);
        item->setCheckState(alarm.enabled ? Qt::Checked : Qt::Unchecked);
        alarms_->addItem(item);
    }
    if (selection >= 0 && selection < alarms_->count())
        alarms_->setCurrentRow(selection);
}

void SettingsDialog::editAlarm(bool create) {
    const int row = alarms_->currentRow();
    if (!create && row < 0)
        return;
    AlarmEditDialog dialog(create ? Alarm() : draft_.alarms.at(row), this);
    editor_ = &dialog;
    const int outcome = dialog.exec();
    editor_ = nullptr;
    if (outcome != QDialog::Accepted)
        return;
    if (create)
        draft_.alarms.append(dialog.resultAlarm());
    else
        draft_.alarms[row] = dialog.resultAlarm();
    refreshAlarms();
}

void SettingsDialog::markAlarmFired(const Alarm &fired) {
    if (editor_)
        editor_->markAlarmFired(fired);
    for (auto &alarm : draft_.alarms)
        if (alarm.id == fired.id && alarm.time == fired.time && alarm.repeat == fired.repeat &&
            alarm.weekdays == fired.weekdays)
            alarm.enabled = false;
    refreshAlarms();
}

AboutDialog::AboutDialog(QWidget *parent) : QDialog(parent) {
    setObjectName("aboutDialog");
    setWindowTitle(QStringLiteral("浮动时钟 — 关于与许可"));
    auto *layout = new QVBoxLayout(this);
    auto *description = new QLabel(
        QStringLiteral("浮动时钟 %1\nQt %2\n应用许可证：GNU AGPL-3.0").arg(FC_VERSION, qVersion()));
    description->setTextInteractionFlags(Qt::TextSelectableByMouse);
    layout->addWidget(description);
    auto *source = new QLabel(
        QStringLiteral("<a href=\"https://github.com/sunging/floating_clock\">源码与构建说明</a>"));
    source->setOpenExternalLinks(true);
    layout->addWidget(source);
    auto *text = new QPlainTextEdit;
    text->setObjectName("licenseText");
    text->setReadOnly(true);
    QFile notices(":/licenses/notices.txt");
    if (notices.open(QIODevice::ReadOnly))
        text->setPlainText(QString::fromUtf8(notices.readAll()));
    else
        text->setPlainText(QStringLiteral("完整许可说明位于发行包的 licenses 目录。"));
    layout->addWidget(text, 1);
    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Close);
    buttons->button(QDialogButtonBox::Close)->setText(QStringLiteral("关闭"));
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
    auto *save = buttons->addButton(QStringLiteral("导出许可文本…"), QDialogButtonBox::ActionRole);
    save->setEnabled(notices.isOpen());
    connect(save, &QPushButton::clicked, this, [this, text] {
        const auto path = QFileDialog::getSaveFileName(
            this, QStringLiteral("导出许可文本"), "FloatingClock-licenses.txt",
            QStringLiteral("文本文件 (*.txt)"), nullptr, QFileDialog::DontUseNativeDialog);
        if (path.isEmpty())
            return;
        QSaveFile file(path);
        const auto bytes = text->toPlainText().toUtf8();
        if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size() || !file.commit())
            QMessageBox::warning(this, QStringLiteral("导出失败"), file.errorString());
    });
    layout->addWidget(buttons);
    resize(QSize(700, 520).boundedTo(screen()->availableGeometry().size() - QSize(40, 40)));
}

ControlPanel::ControlPanel(Timers &timers, bool hasTray, QWidget *parent)
    : QDialog(parent), timers_(timers), hasTray_(hasTray) {
    setWindowTitle(QStringLiteral("浮动时钟 — 控制面板"));
    auto *layout = new QVBoxLayout(this);
    auto *form = new QFormLayout;
    mode_ = new QComboBox;
    mode_->addItem(QStringLiteral("时钟"), "clock");
    mode_->addItem(QStringLiteral("倒计时"), "countdown");
    mode_->addItem(QStringLiteral("秒表"), "stopwatch");
    mode_->setCurrentIndex(std::max(0, mode_->findData(timers.displayMode)));
    connect(mode_, &QComboBox::currentIndexChanged, this, [this] {
        timers_.displayMode = mode_->currentData().toString();
        emit timersChanged();
    });
    form->addRow(QStringLiteral("浮窗显示"), mode_);
    layout->addLayout(form);
    auto *tabs = new QTabWidget;
    auto *countdownPage = new QWidget;
    auto *countdownLayout = new QVBoxLayout(countdownPage);
    countdown_ = new QLabel;
    countdown_->setAlignment(Qt::AlignCenter);
    countdown_->setStyleSheet("font-size: 28px;");
    countdownLayout->addWidget(countdown_);
    auto *durationRow = new QHBoxLayout;
    auto makeDuration = [durationRow](int maximum, const QString &suffix) {
        auto *spin = new QSpinBox;
        spin->setRange(0, maximum);
        spin->setSuffix(suffix);
        durationRow->addWidget(spin);
        return spin;
    };
    hours_ = makeDuration(99, QStringLiteral(" 时"));
    minutes_ = makeDuration(59, QStringLiteral(" 分"));
    seconds_ = makeDuration(59, QStringLiteral(" 秒"));
    const qint64 seconds = timers_.countdownDuration() / 1000;
    hours_->setValue(int(seconds / 3600));
    minutes_->setValue(int(seconds / 60 % 60));
    seconds_->setValue(int(seconds % 60));
    countdownLayout->addLayout(durationRow);
    auto *actions = new QHBoxLayout;
    countdownAction_ = button(actions, QString(), [this] {
        if (timers_.countdownState() == Timers::State::Running)
            timers_.pauseCountdown();
        else if (timers_.countdownState() == Timers::State::Paused)
            timers_.resumeCountdown();
        else {
            const qint64 millis =
                (hours_->value() * 3600LL + minutes_->value() * 60 + seconds_->value()) * 1000;
            if (millis <= 0) {
                showStatus(QStringLiteral("请设置至少 1 秒的倒计时。"));
                return;
            }
            timers_.startCountdown(millis);
        }
        emit timersChanged();
        refresh();
    });
    button(actions, QStringLiteral("重置"), [this] {
        timers_.resetCountdown();
        emit timersChanged();
        refresh();
    });
    countdownLayout->addLayout(actions);
    countdownLayout->addStretch();
    tabs->addTab(countdownPage, QStringLiteral("倒计时"));
    auto *stopwatchPage = new QWidget;
    auto *stopwatchLayout = new QVBoxLayout(stopwatchPage);
    stopwatch_ = new QLabel;
    stopwatch_->setAlignment(Qt::AlignCenter);
    stopwatch_->setStyleSheet("font-size: 28px;");
    stopwatchLayout->addWidget(stopwatch_);
    actions = new QHBoxLayout;
    stopwatchAction_ = button(actions, QString(), [this] {
        if (timers_.stopwatchRunning())
            timers_.pauseStopwatch();
        else
            timers_.startStopwatch();
        emit timersChanged();
        refresh();
    });
    button(actions, QStringLiteral("计次"), [this] {
        timers_.lap();
        emit timersChanged();
        refresh();
    });
    button(actions, QStringLiteral("重置"), [this] {
        timers_.resetStopwatch();
        emit timersChanged();
        refresh();
    });
    stopwatchLayout->addLayout(actions);
    laps_ = new QListWidget;
    stopwatchLayout->addWidget(laps_, 1);
    tabs->addTab(stopwatchPage, QStringLiteral("秒表"));
    layout->addWidget(tabs, 1);
    actions = new QHBoxLayout;
    button(actions, QStringLiteral("设置…"), [this] { emit settingsRequested(); });
    button(actions, QStringLiteral("移动浮窗"), [this] { emit moveRequested(); });
    button(actions, QStringLiteral("停止提醒"), [this] { emit stopRequested(); });
    layout->addLayout(actions);
    actions = new QHBoxLayout;
    button(actions, QStringLiteral("导入旧配置…"), [this] { emit importRequested(); });
    button(actions, QStringLiteral("关于与许可…"), [this] {
        auto *dialog = new AboutDialog(this);
        dialog->setAttribute(Qt::WA_DeleteOnClose);
        dialog->open();
    });
    button(actions, QStringLiteral("退出"), [this] { emit quitRequested(); });
    layout->addLayout(actions);
    status_ = new QLabel;
    status_->setWordWrap(true);
    status_->setTextInteractionFlags(Qt::TextSelectableByMouse);
    layout->addWidget(status_);
    resize(QSize(500, 360).boundedTo(screen()->availableGeometry().size() - QSize(40, 40)));
    refresh();
}

void ControlPanel::refresh() {
    const auto state = timers_.countdownState();
    QString suffix;
    if (state == Timers::State::Paused)
        suffix = QStringLiteral("（已暂停）");
    else if (state == Timers::State::Finished)
        suffix = QStringLiteral("（已完成）");
    countdown_->setText(Timers::formatDuration(timers_.countdownRemaining()) + suffix);
    countdownAction_->setText(state == Timers::State::Running  ? QStringLiteral("暂停")
                              : state == Timers::State::Paused ? QStringLiteral("继续")
                                                               : QStringLiteral("开始"));
    const bool editable = state == Timers::State::Idle || state == Timers::State::Finished;
    hours_->setEnabled(editable);
    minutes_->setEnabled(editable);
    seconds_->setEnabled(editable);
    stopwatch_->setText(Timers::formatDuration(timers_.stopwatchElapsed(), true));
    stopwatchAction_->setText(timers_.stopwatchRunning() ? QStringLiteral("暂停")
                                                         : QStringLiteral("开始/继续"));
    if (laps_->count() != timers_.laps().size()) {
        laps_->clear();
        qint64 previous = 0;
        int number = 0;
        for (qint64 lap : timers_.laps()) {
            laps_->addItem(QStringLiteral("%1   %2   +%3")
                               .arg(++number)
                               .arg(Timers::formatDuration(lap, true),
                                    Timers::formatDuration(lap - previous, true)));
            previous = lap;
        }
    }
    const QSignalBlocker block(mode_);
    mode_->setCurrentIndex(mode_->findData(timers_.displayMode));
}

void ControlPanel::showStatus(const QString &message) {
    status_->setText(message);
}

void ControlPanel::setTrayAvailable(bool available) {
    hasTray_ = available;
}

void ControlPanel::reject() {
    // Escape must not strand a click-through clock without its only control surface.
    if (hasTray_)
        QDialog::reject();
    else
        emit quitRequested();
}

void ControlPanel::closeEvent(QCloseEvent *event) {
    if (hasTray_)
        QDialog::closeEvent(event);
    else {
        event->ignore();
        emit quitRequested();
    }
}

} // namespace fc
