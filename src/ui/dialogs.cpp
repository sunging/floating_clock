#include "ui/dialogs.h"
#include "core/i18n.h"
#include "ui/translation.h"
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
const char *const DayNames[]{
    QT_TRANSLATE_NOOP("FloatingClock", "Mon"), QT_TRANSLATE_NOOP("FloatingClock", "Tue"),
    QT_TRANSLATE_NOOP("FloatingClock", "Wed"), QT_TRANSLATE_NOOP("FloatingClock", "Thu"),
    QT_TRANSLATE_NOOP("FloatingClock", "Fri"), QT_TRANSLATE_NOOP("FloatingClock", "Sat"),
    QT_TRANSLATE_NOOP("FloatingClock", "Sun")};

QString repeatName(const Alarm &alarm) {
    if (alarm.repeat == "once")
        return I18n::tr("Once");
    if (alarm.repeat == "weekdays")
        return I18n::tr("Weekdays");
    if (alarm.repeat == "custom") {
        QStringList days;
        for (int day : alarm.weekdays)
            days.append(I18n::tr(DayNames[day]));
        return days.join(' ');
    }
    return I18n::tr("Daily");
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

QSpinBox *integer(QFormLayout *form, const char *label, int &value, int low, int high,
                  const std::function<void()> &changed = {}) {
    auto *spin = new QSpinBox;
    spin->setRange(low, high);
    spin->setValue(value);
    QObject::connect(spin, &QSpinBox::valueChanged, spin, [&value, changed](int input) {
        value = input;
        if (changed)
            changed();
    });
    addTranslatedRow(form, label, spin);
    return spin;
}

void real(QFormLayout *form, const char *label, double &value, double low, double high,
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
    addTranslatedRow(form, label, spin);
}

QCheckBox *boolean(QFormLayout *form, const char *label, bool &value,
                   const std::function<void()> &changed = {}) {
    auto *check = translatedWidget<QCheckBox>(label);
    check->setChecked(value);
    QObject::connect(check, &QCheckBox::toggled, check, [&value, changed](bool input) {
        value = input;
        if (changed)
            changed();
    });
    form->addRow(check);
    return check;
}

void color(QFormLayout *form, const char *label, QString &value,
           const std::function<void()> &changed) {
    auto *button = new QPushButton(value);
    auto style = [button, &value] {
        const QColor color(value);
        button->setText(value);
        button->setStyleSheet(QStringLiteral("background: %1; color: %2;")
                                  .arg(value, color.lightness() > 128 ? "black" : "white"));
    };
    style();
    QObject::connect(
        button, &QPushButton::clicked, button, [button, &value, changed, style, label] {
            const QColor selected = QColorDialog::getColor(QColor(value), button, I18n::tr(label),
                                                           QColorDialog::DontUseNativeDialog);
            if (!selected.isValid())
                return;
            value = selected.name();
            style();
            changed();
        });
    addTranslatedRow(form, label, button);
}

QComboBox *choice(QFormLayout *form, const char *label, QString &value,
                  const QList<QPair<const char *, QString>> &options,
                  const std::function<void()> &changed = {}) {
    auto *combo = new QComboBox;
    for (const auto &option : options)
        addTranslatedItem(combo, option.first, option.second);
    combo->setCurrentIndex(std::max(0, combo->findData(value)));
    QObject::connect(combo, &QComboBox::currentIndexChanged, combo, [&value, combo, changed] {
        value = combo->currentData().toString();
        if (changed)
            changed();
    });
    addTranslatedRow(form, label, combo);
    return combo;
}

QPushButton *button(QHBoxLayout *row, const char *label, const std::function<void()> &action) {
    auto *result = new QPushButton;
    if (label)
        bindText(result, label);
    QObject::connect(result, &QPushButton::clicked, result, action);
    row->addWidget(result);
    return result;
}
} // namespace

AlarmEditDialog::AlarmEditDialog(const Alarm &alarm, QWidget *parent)
    : QDialog(parent), original_(alarm) {
    bindText(this, QT_TRANSLATE_NOOP("FloatingClock", "Edit alarm"), "windowTitle");
    auto *outer = new QVBoxLayout(this);
    auto *body = new QWidget;
    auto *layout = new QVBoxLayout(body);
    auto *form = new QFormLayout;
    layout->addLayout(form);
    time_ = new QTimeEdit(QTime::fromString(alarm.time, "HH:mm"));
    time_->setObjectName("alarmTime");
    time_->setDisplayFormat("HH:mm");
    addTranslatedRow(form, QT_TRANSLATE_NOOP("FloatingClock", "Time"), time_);
    label_ = new QLineEdit(alarm.label);
    label_->setObjectName("alarmLabel");
    addTranslatedRow(form, QT_TRANSLATE_NOOP("FloatingClock", "Name"), label_);
    content_ = new QPlainTextEdit(alarm.content);
    content_->setObjectName("alarmContent");
    content_->setMinimumHeight(100);
    addTranslatedRow(form, QT_TRANSLATE_NOOP("FloatingClock", "Content"), content_);
    repeat_ = new QComboBox;
    repeat_->setObjectName("alarmRepeat");
    addTranslatedItem(repeat_, QT_TRANSLATE_NOOP("FloatingClock", "Once"), "once");
    addTranslatedItem(repeat_, QT_TRANSLATE_NOOP("FloatingClock", "Daily"), "daily");
    addTranslatedItem(repeat_, QT_TRANSLATE_NOOP("FloatingClock", "Weekdays"), "weekdays");
    addTranslatedItem(repeat_, QT_TRANSLATE_NOOP("FloatingClock", "Custom weekdays"), "custom");
    repeat_->setCurrentIndex(repeat_->findData(alarm.repeat));
    addTranslatedRow(form, QT_TRANSLATE_NOOP("FloatingClock", "Repeat"), repeat_);
    auto *days = new QHBoxLayout;
    for (int day = 0; day < 7; ++day) {
        auto *check = translatedWidget<QCheckBox>(DayNames[day]);
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
    inherit_ = translatedWidget<QCheckBox>(
        QT_TRANSLATE_NOOP("FloatingClock", "Use the global reminder timeout"));
    inherit_->setObjectName("inheritTimeout");
    inherit_->setChecked(!alarm.timeoutSeconds);
    form->addRow(inherit_);
    timeout_ = new QSpinBox;
    timeout_->setObjectName("alarmTimeout");
    timeout_->setRange(1, 3600);
    bindText(timeout_, QT_TRANSLATE_NOOP("FloatingClock", " s"), "suffix");
    timeout_->setValue(alarm.timeoutSeconds.value_or(60));
    timeout_->setEnabled(alarm.timeoutSeconds.has_value());
    addTranslatedRow(form, QT_TRANSLATE_NOOP("FloatingClock", "Stop automatically"), timeout_);
    connect(inherit_, &QCheckBox::toggled, timeout_,
            [this](bool checked) { timeout_->setEnabled(!checked); });
    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
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
        result.label = I18n::tr("Alarm");
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
        QMessageBox::warning(this, I18n::tr("Alarm"), I18n::tr("Select at least one weekday."));
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
    bindText(this, QT_TRANSLATE_NOOP("FloatingClock", "Floating Clock — Settings"), "windowTitle");
    auto *layout = new QVBoxLayout(this);
    auto *tabs = new QTabWidget;
    layout->addWidget(tabs, 1);
    const auto preview = [this] { emit previewRequested(draft_); };
    QFormLayout *form;
    addTranslatedTab(tabs, scrollPage(&form), QT_TRANSLATE_NOOP("FloatingClock", "General"));
    choice(form, QT_TRANSLATE_NOOP("FloatingClock", "Language"), draft_.language,
           {{QT_TRANSLATE_NOOP("FloatingClock", "Follow system"), "system"},
            {QT_TRANSLATE_NOOP("FloatingClock", "English"), "en"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Simplified Chinese"), "zh_CN"}},
           preview)
        ->setObjectName("language");
    auto *languageHint = translatedWidget<QLabel>(QT_TRANSLATE_NOOP(
        "FloatingClock",
        "Language changes are previewed immediately. Cancel restores the previous language."));
    languageHint->setWordWrap(true);
    form->addRow(languageHint);
    boolean(form, QT_TRANSLATE_NOOP("FloatingClock", "Click through"), draft_.clickThrough)
        ->setEnabled(capabilities.clickThrough);
    boolean(form, QT_TRANSLATE_NOOP("FloatingClock", "Start at login"), draft_.startOnBoot);
    boolean(form, QT_TRANSLATE_NOOP("FloatingClock", "Allow reminders when the screen is off"),
            draft_.ringWhenScreenOff);
    auto *power = new QLabel;
    bindTranslation(power, [power, detectable = capabilities.displayPower] {
        power->setText(detectable ? I18n::tr("By default, screen-off alarms stay silent and "
                                             "one-shot alarms are not consumed.")
                                  : I18n::tr("Display power cannot be detected on this system. "
                                             "Unknown display power is treated as on."));
    });
    power->setWordWrap(true);
    form->addRow(power);
    if (!capabilities.explanation.isEmpty()) {
        auto *notice = new QLabel;
        bindTranslation(notice, [notice, source = capabilities.explanation] {
            notice->setText(I18n::tr(source.toUtf8().constData()));
        });
        notice->setWordWrap(true);
        form->addRow(notice);
    }

    addTranslatedTab(tabs, scrollPage(&form), QT_TRANSLATE_NOOP("FloatingClock", "Appearance"));
    integer(form, QT_TRANSLATE_NOOP("FloatingClock", "Font size"), draft_.fontSize, 8, 400, preview)
        ->setObjectName("fontSize");
    real(form, QT_TRANSLATE_NOOP("FloatingClock", "Window opacity"), draft_.opacity, 0.1, 1.0,
         preview);
    color(form, QT_TRANSLATE_NOOP("FloatingClock", "Text color"), draft_.color, preview);
    auto *autoColor =
        boolean(form, QT_TRANSLATE_NOOP("FloatingClock", "Adapt text color to the background"),
                draft_.autoColor, preview);
    autoColor->setEnabled(capabilities.screenSampling);
    color(form, QT_TRANSLATE_NOOP("FloatingClock", "Color on dark backgrounds"),
          draft_.darkBackgroundColor, preview);
    color(form, QT_TRANSLATE_NOOP("FloatingClock", "Color on light backgrounds"),
          draft_.lightBackgroundColor, preview);
    boolean(form, QT_TRANSLATE_NOOP("FloatingClock", "Show seconds"), draft_.showSeconds, preview);
    boolean(form, QT_TRANSLATE_NOOP("FloatingClock", "Show date"), draft_.showDate, preview);

    addTranslatedTab(tabs, scrollPage(&form),
                     QT_TRANSLATE_NOOP("FloatingClock", "Reminder appearance"));
    color(form, QT_TRANSLATE_NOOP("FloatingClock", "Text color"), draft_.popupTextColor, preview);
    color(form, QT_TRANSLATE_NOOP("FloatingClock", "Background color"), draft_.popupBackgroundColor,
          preview);
    real(form, QT_TRANSLATE_NOOP("FloatingClock", "Background opacity"), draft_.popupOpacity, 0.0,
         1.0, preview);
    real(form, QT_TRANSLATE_NOOP("FloatingClock", "Font scale"), draft_.popupFontScale, 0.5, 3.0,
         preview);
    boolean(form, QT_TRANSLATE_NOOP("FloatingClock", "Flash"), draft_.popupFlash, preview);
    choice(form, QT_TRANSLATE_NOOP("FloatingClock", "Layout"), draft_.popupLayout,
           {{QT_TRANSLATE_NOOP("FloatingClock", "Name/content above time"), "label_time"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Time above name/content"), "time_label"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Name/content only"), "label_only"}},
           preview);
    auto *popupPreview = translatedWidget<QPushButton>(
        QT_TRANSLATE_NOOP("FloatingClock", "Preview reminder (3 seconds)"));
    connect(popupPreview, &QPushButton::clicked, this,
            [this] { emit reminderPreviewRequested(draft_); });
    form->addRow(popupPreview);

    addTranslatedTab(tabs, scrollPage(&form),
                     QT_TRANSLATE_NOOP("FloatingClock", "Sound and timeout"));
    choice(form, QT_TRANSLATE_NOOP("FloatingClock", "Sound"), draft_.soundMode,
           {{QT_TRANSLATE_NOOP("FloatingClock", "Silent"), "silent"},
            {QT_TRANSLATE_NOOP("FloatingClock", "System/built-in sound"), "system"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Custom WAV"), "custom"}});
#ifdef Q_OS_WIN
    choice(form, QT_TRANSLATE_NOOP("FloatingClock", "System sound"), draft_.soundAlias,
           {{QT_TRANSLATE_NOOP("FloatingClock", "Error"), "SystemHand"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Asterisk"), "SystemAsterisk"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Exclamation"), "SystemExclamation"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Question"), "SystemQuestion"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Default"), "SystemDefault"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Windows startup"), "SystemStart"},
            {QT_TRANSLATE_NOOP("FloatingClock", "Windows exit"), "SystemExit"}});
#endif
    auto *soundPath = new QLineEdit(draft_.soundPath);
    connect(soundPath, &QLineEdit::textChanged, this,
            [this](const QString &path) { draft_.soundPath = path; });
    addTranslatedRow(form, QT_TRANSLATE_NOOP("FloatingClock", "WAV file"), soundPath);
    auto *browse = translatedWidget<QPushButton>(QT_TRANSLATE_NOOP("FloatingClock", "Browse…"));
    connect(browse, &QPushButton::clicked, this, [this, soundPath] {
        // Native Windows file dialogs can block Qt timers, including reminder expiration.
        const auto path = QFileDialog::getOpenFileName(
            this, I18n::tr("Choose a reminder sound"), draft_.soundPath,
            I18n::tr("WAV audio (*.wav)"), nullptr, QFileDialog::DontUseNativeDialog);
        if (!path.isEmpty())
            soundPath->setText(path);
    });
    form->addRow(browse);
    auto *soundPreview = translatedWidget<QPushButton>(
        QT_TRANSLATE_NOOP("FloatingClock", "Test sound (up to 3 seconds)"));
    connect(soundPreview, &QPushButton::clicked, this,
            [this] { emit soundPreviewRequested(draft_); });
    form->addRow(soundPreview);
    integer(form, QT_TRANSLATE_NOOP("FloatingClock", "Default timeout (seconds)"),
            draft_.alarmTimeoutSeconds, 1, 3600)
        ->setObjectName("defaultTimeout");

    auto *alarmPage = new QWidget;
    auto *alarmLayout = new QVBoxLayout(alarmPage);
    alarms_ = new QListWidget;
    alarms_->setObjectName("alarmList");
    alarms_->setWordWrap(true);
    alarmLayout->addWidget(alarms_, 1);
    auto *row = new QHBoxLayout;
    button(row, QT_TRANSLATE_NOOP("FloatingClock", "Add"), [this] { editAlarm(true); });
    button(row, QT_TRANSLATE_NOOP("FloatingClock", "Edit"), [this] { editAlarm(false); });
    button(row, QT_TRANSLATE_NOOP("FloatingClock", "Delete"), [this] {
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
    bindTranslation(this, [this] { refreshAlarms(); });
    addTranslatedTab(tabs, alarmPage, QT_TRANSLATE_NOOP("FloatingClock", "Alarms"));
    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Ok | QDialogButtonBox::Cancel);
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
                                    ? I18n::tr("Stop after %1 s").arg(*alarm.timeoutSeconds)
                                    : I18n::tr("Global timeout");
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
    bindText(this, QT_TRANSLATE_NOOP("FloatingClock", "Floating Clock — About and licenses"),
             "windowTitle");
    auto *layout = new QVBoxLayout(this);
    auto *description = new QLabel;
    bindTranslation(description, [description] {
        description->setText(I18n::tr("Floating Clock %1\nQt %2\nApplication license: GNU AGPL-3.0")
                                 .arg(FC_VERSION, qVersion()));
    });
    description->setTextInteractionFlags(Qt::TextSelectableByMouse);
    layout->addWidget(description);
    auto *source = translatedWidget<QLabel>(QT_TRANSLATE_NOOP(
        "FloatingClock", "<a href=\"https://github.com/sunging/floating_clock\">Source code and "
                         "build instructions</a>"));
    source->setOpenExternalLinks(true);
    layout->addWidget(source);
    auto *text = new QPlainTextEdit;
    text->setObjectName("licenseText");
    text->setReadOnly(true);
    QFile notices(":/licenses/notices.txt");
    if (notices.open(QIODevice::ReadOnly))
        text->setPlainText(QString::fromUtf8(notices.readAll()));
    else
        bindText(text,
                 QT_TRANSLATE_NOOP(
                     "FloatingClock",
                     "Complete license notices are available in the package's licenses directory."),
                 "plainText");
    layout->addWidget(text, 1);
    auto *buttons = new QDialogButtonBox(QDialogButtonBox::Close);
    connect(buttons, &QDialogButtonBox::rejected, this, &QDialog::reject);
    auto *save = buttons->addButton(QString(), QDialogButtonBox::ActionRole);
    bindText(save, QT_TRANSLATE_NOOP("FloatingClock", "Export license text…"));
    save->setEnabled(notices.isOpen());
    connect(save, &QPushButton::clicked, this, [this, text] {
        const auto path = QFileDialog::getSaveFileName(
            this, I18n::tr("Export license text"), "FloatingClock-licenses.txt",
            I18n::tr("Text files (*.txt)"), nullptr, QFileDialog::DontUseNativeDialog);
        if (path.isEmpty())
            return;
        QSaveFile file(path);
        const auto bytes = text->toPlainText().toUtf8();
        if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size() || !file.commit())
            QMessageBox::warning(this, I18n::tr("Export failed"), file.errorString());
    });
    layout->addWidget(buttons);
    resize(QSize(700, 520).boundedTo(screen()->availableGeometry().size() - QSize(40, 40)));
}

ControlPanel::ControlPanel(Timers &timers, bool hasTray, QWidget *parent)
    : QDialog(parent), timers_(timers), hasTray_(hasTray) {
    bindText(this, QT_TRANSLATE_NOOP("FloatingClock", "Floating Clock — Control panel"),
             "windowTitle");
    auto *layout = new QVBoxLayout(this);
    auto *form = new QFormLayout;
    mode_ = new QComboBox;
    addTranslatedItem(mode_, QT_TRANSLATE_NOOP("FloatingClock", "Clock"), "clock");
    addTranslatedItem(mode_, QT_TRANSLATE_NOOP("FloatingClock", "Countdown"), "countdown");
    addTranslatedItem(mode_, QT_TRANSLATE_NOOP("FloatingClock", "Stopwatch"), "stopwatch");
    mode_->setCurrentIndex(std::max(0, mode_->findData(timers.displayMode)));
    connect(mode_, &QComboBox::currentIndexChanged, this, [this] {
        timers_.displayMode = mode_->currentData().toString();
        emit timersChanged();
    });
    addTranslatedRow(form, QT_TRANSLATE_NOOP("FloatingClock", "Floating display"), mode_);
    layout->addLayout(form);
    auto *tabs = new QTabWidget;
    auto *countdownPage = new QWidget;
    auto *countdownLayout = new QVBoxLayout(countdownPage);
    countdown_ = new QLabel;
    countdown_->setAlignment(Qt::AlignCenter);
    countdown_->setStyleSheet("font-size: 28px;");
    countdownLayout->addWidget(countdown_);
    auto *durationRow = new QHBoxLayout;
    auto makeDuration = [durationRow](int maximum, const char *suffix) {
        auto *spin = new QSpinBox;
        spin->setRange(0, maximum);
        bindText(spin, suffix, "suffix");
        durationRow->addWidget(spin);
        return spin;
    };
    hours_ = makeDuration(99, QT_TRANSLATE_NOOP("FloatingClock", " h"));
    minutes_ = makeDuration(59, QT_TRANSLATE_NOOP("FloatingClock", " min"));
    seconds_ = makeDuration(59, QT_TRANSLATE_NOOP("FloatingClock", " s"));
    const qint64 seconds = timers_.countdownDuration() / 1000;
    hours_->setValue(int(seconds / 3600));
    minutes_->setValue(int(seconds / 60 % 60));
    seconds_->setValue(int(seconds % 60));
    countdownLayout->addLayout(durationRow);
    auto *actions = new QHBoxLayout;
    countdownAction_ = button(actions, nullptr, [this] {
        if (timers_.countdownState() == Timers::State::Running)
            timers_.pauseCountdown();
        else if (timers_.countdownState() == Timers::State::Paused)
            timers_.resumeCountdown();
        else {
            const qint64 millis =
                (hours_->value() * 3600LL + minutes_->value() * 60 + seconds_->value()) * 1000;
            if (millis <= 0) {
                showStatus(I18n::tr("Set a countdown of at least 1 second."));
                return;
            }
            timers_.startCountdown(millis);
        }
        emit timersChanged();
        refresh();
    });
    button(actions, QT_TRANSLATE_NOOP("FloatingClock", "Reset"), [this] {
        timers_.resetCountdown();
        emit timersChanged();
        refresh();
    });
    countdownLayout->addLayout(actions);
    countdownLayout->addStretch();
    addTranslatedTab(tabs, countdownPage, QT_TRANSLATE_NOOP("FloatingClock", "Countdown"));
    auto *stopwatchPage = new QWidget;
    auto *stopwatchLayout = new QVBoxLayout(stopwatchPage);
    stopwatch_ = new QLabel;
    stopwatch_->setAlignment(Qt::AlignCenter);
    stopwatch_->setStyleSheet("font-size: 28px;");
    stopwatchLayout->addWidget(stopwatch_);
    actions = new QHBoxLayout;
    stopwatchAction_ = button(actions, nullptr, [this] {
        if (timers_.stopwatchRunning())
            timers_.pauseStopwatch();
        else
            timers_.startStopwatch();
        emit timersChanged();
        refresh();
    });
    button(actions, QT_TRANSLATE_NOOP("FloatingClock", "Lap"), [this] {
        timers_.lap();
        emit timersChanged();
        refresh();
    });
    button(actions, QT_TRANSLATE_NOOP("FloatingClock", "Reset"), [this] {
        timers_.resetStopwatch();
        emit timersChanged();
        refresh();
    });
    stopwatchLayout->addLayout(actions);
    laps_ = new QListWidget;
    stopwatchLayout->addWidget(laps_, 1);
    addTranslatedTab(tabs, stopwatchPage, QT_TRANSLATE_NOOP("FloatingClock", "Stopwatch"));
    layout->addWidget(tabs, 1);
    actions = new QHBoxLayout;
    button(actions, QT_TRANSLATE_NOOP("FloatingClock", "Settings…"),
           [this] { emit settingsRequested(); });
    button(actions, QT_TRANSLATE_NOOP("FloatingClock", "Move clock"),
           [this] { emit moveRequested(); });
    button(actions, QT_TRANSLATE_NOOP("FloatingClock", "Stop reminders"),
           [this] { emit stopRequested(); });
    layout->addLayout(actions);
    actions = new QHBoxLayout;
    button(actions, QT_TRANSLATE_NOOP("FloatingClock", "Import legacy settings…"),
           [this] { emit importRequested(); });
    button(actions, QT_TRANSLATE_NOOP("FloatingClock", "About and licenses…"), [this] {
        auto *dialog = new AboutDialog(this);
        dialog->setAttribute(Qt::WA_DeleteOnClose);
        dialog->open();
    });
    button(actions, QT_TRANSLATE_NOOP("FloatingClock", "Quit"), [this] { emit quitRequested(); });
    layout->addLayout(actions);
    status_ = new QLabel;
    status_->setWordWrap(true);
    status_->setTextInteractionFlags(Qt::TextSelectableByMouse);
    layout->addWidget(status_);
    resize(QSize(500, 360).boundedTo(screen()->availableGeometry().size() - QSize(40, 40)));
    bindTranslation(this, [this] { refresh(); });
}

void ControlPanel::refresh() {
    const auto state = timers_.countdownState();
    QString suffix;
    if (state == Timers::State::Paused)
        suffix = I18n::tr(" (paused)");
    else if (state == Timers::State::Finished)
        suffix = I18n::tr(" (finished)");
    countdown_->setText(Timers::formatDuration(timers_.countdownRemaining()) + suffix);
    countdownAction_->setText(state == Timers::State::Running  ? I18n::tr("Pause")
                              : state == Timers::State::Paused ? I18n::tr("Resume")
                                                               : I18n::tr("Start"));
    const bool editable = state == Timers::State::Idle || state == Timers::State::Finished;
    hours_->setEnabled(editable);
    minutes_->setEnabled(editable);
    seconds_->setEnabled(editable);
    stopwatch_->setText(Timers::formatDuration(timers_.stopwatchElapsed(), true));
    stopwatchAction_->setText(timers_.stopwatchRunning() ? I18n::tr("Pause")
                                                         : I18n::tr("Start/resume"));
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
