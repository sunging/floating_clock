#pragma once

#include "core/config_store.h"
#include "core/timers.h"
#include "platform/services.h"
#include "ui/clock_window.h"
#include "ui/dialogs.h"
#include <QAction>
#include <QMenu>
#include <QPointer>
#include <QSystemTrayIcon>
#include <QTimer>
#include <memory>

namespace fc {

class ApplicationController : public QObject {
    Q_OBJECT
public:
    ApplicationController(const ConfigStore &store, const TimeSource &time,
                          PlatformServices &platform, SoundService &sound,
                          bool systemIntegration = true);
    ~ApplicationController() override;
    void tick();
    void showControl();
    void openSettings();
    void stopReminders();
    void setMoveMode(bool enabled);
    void applyClickThrough();
    void preview(const Config &config);
    Config &config();
    Timers &timers();
    ClockWindow &clock();
    const ReminderController &reminders() const;

private:
    void buildTray();
    void watchScreen(QScreen *screen);
    void scheduleRestore();
    void syncReminders();
    void saveConfig();
    void saveRuntime();
    void report(const QString &message);
    void importConfig();
    void stopPreview();
    void quit();
    const ConfigStore &store_;
    const TimeSource &time_;
    PlatformServices &platform_;
    SoundService &sound_;
    Config config_;
    Config appearance_;
    AlarmScheduler scheduler_;
    ReminderController reminders_;
    Timers timers_;
    std::unique_ptr<ClockWindow> clock_;
    std::unique_ptr<ControlPanel> panel_;
    std::unique_ptr<QMenu> menu_;
    QPointer<SettingsDialog> settings_;
    QSystemTrayIcon *tray_ = nullptr;
    QAction *moveAction_ = nullptr;
    QAction *throughAction_ = nullptr;
    QAction *stopAction_ = nullptr;
    QTimer tickTimer_;
    QTimer restoreTimer_;
    QTimer previewTimer_;
    QTimer soundPreviewTimer_;
    bool integration_;
    bool trayAvailable_ = false;
    bool moveMode_ = false;
    bool previewing_ = false;
    bool ringing_ = false;
    std::optional<ReminderSound> reminderSound_;
    bool suppressCountdown_ = false;
    qint64 lastTick_ = 0;
    qint64 lastSample_ = 0;
    qint64 lastSnapshot_ = 0;
    QString lastError_;
};

} // namespace fc
