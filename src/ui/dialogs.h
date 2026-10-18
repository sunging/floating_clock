#pragma once

#include "core/timers.h"
#include "platform/services.h"
#include <QCheckBox>
#include <QComboBox>
#include <QDialog>
#include <QLabel>
#include <QLineEdit>
#include <QListWidget>
#include <QPlainTextEdit>
#include <QPointer>
#include <QPushButton>
#include <QSpinBox>
#include <QTimeEdit>

namespace fc {

class AboutDialog : public QDialog {
public:
    explicit AboutDialog(QWidget *parent = nullptr);
};

class AlarmEditDialog : public QDialog {
    Q_OBJECT
public:
    explicit AlarmEditDialog(const Alarm &alarm, QWidget *parent = nullptr);
    Alarm resultAlarm() const;
    void markAlarmFired(const Alarm &alarm);

private:
    void accept() override;
    Alarm original_;
    QTimeEdit *time_;
    QLineEdit *label_;
    QPlainTextEdit *content_;
    QComboBox *repeat_;
    QVector<QCheckBox *> days_;
    QCheckBox *inherit_;
    QSpinBox *timeout_;
};

class SettingsDialog : public QDialog {
    Q_OBJECT
public:
    SettingsDialog(const Config &config, const Capabilities &capabilities,
                   QWidget *parent = nullptr);
    Config resultConfig() const;
    void markAlarmFired(const Alarm &alarm);

signals:
    void previewRequested(const fc::Config &config);
    void reminderPreviewRequested(const fc::Config &config);
    void soundPreviewRequested(const fc::Config &config);

private:
    void refreshAlarms();
    void editAlarm(bool create);
    Config draft_;
    QListWidget *alarms_;
    QPointer<AlarmEditDialog> editor_;
};

class ControlPanel : public QDialog {
    Q_OBJECT
public:
    explicit ControlPanel(Timers &timers, bool hasTray, QWidget *parent = nullptr);
    void refresh();
    void showStatus(const QString &message);
    void setTrayAvailable(bool available);
    void reject() override;

signals:
    void timersChanged();
    void settingsRequested();
    void importRequested();
    void quitRequested();
    void stopRequested();
    void moveRequested();

protected:
    void closeEvent(QCloseEvent *event) override;

private:
    Timers &timers_;
    bool hasTray_;
    QComboBox *mode_;
    QSpinBox *hours_;
    QSpinBox *minutes_;
    QSpinBox *seconds_;
    QLabel *countdown_;
    QLabel *stopwatch_;
    QPushButton *countdownAction_;
    QPushButton *stopwatchAction_;
    QListWidget *laps_;
    QLabel *status_;
};

} // namespace fc
