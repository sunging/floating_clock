#include "app.h"

#include <QApplication>
#include <QFileDialog>
#include <QGuiApplication>
#include <QScreen>
#include <QSignalBlocker>
#include <QWindow>

namespace fc {

ApplicationController::ApplicationController(const ConfigStore &store, const TimeSource &time,
                                             PlatformServices &platform, SoundService &sound,
                                             bool systemIntegration)
    : store_(store), time_(time), platform_(platform), sound_(sound), timers_(time),
      integration_(systemIntegration) {
    QString warning;
    config_ = store_.load(&warning);
    appearance_ = config_;
    timers_.restore(store_.loadRuntime(&warning));
    clock_ = std::make_unique<ClockWindow>();
    if (!integration_)
        clock_->setAttribute(Qt::WA_DontShowOnScreen);
    clock_->applyConfig(config_);
    clock_->show();
    const bool hasTray = integration_ && QSystemTrayIcon::isSystemTrayAvailable();
    trayAvailable_ = hasTray;
    panel_ = std::make_unique<ControlPanel>(timers_, hasTray);
    connect(panel_.get(), &ControlPanel::settingsRequested, this,
            &ApplicationController::openSettings);
    connect(panel_.get(), &ControlPanel::quitRequested, this, &ApplicationController::quit);
    connect(panel_.get(), &ControlPanel::importRequested, this,
            &ApplicationController::importConfig);
    connect(panel_.get(), &ControlPanel::stopRequested, this,
            &ApplicationController::stopReminders);
    connect(panel_.get(), &ControlPanel::moveRequested, this, [this] { setMoveMode(!moveMode_); });
    connect(panel_.get(), &ControlPanel::timersChanged, this, [this] {
        saveRuntime();
        tick();
    });
    connect(clock_.get(), &ClockWindow::controlRequested, this,
            &ApplicationController::showControl);
    connect(clock_.get(), &ClockWindow::dismissed, this, &ApplicationController::stopReminders);
    connect(clock_.get(), &ClockWindow::moved, this, [this](const QPoint &position) {
        if (platform_.capabilities().positioning) {
            config_.posX = appearance_.posX = position.x();
            config_.posY = appearance_.posY = position.y();
            clock_->applyConfig(appearance_);
            saveConfig();
        }
        setMoveMode(false);
    });
    connect(&sound_, &SoundService::failed, this, &ApplicationController::report);
    connect(qApp, &QCoreApplication::aboutToQuit, this, [this] {
        saveRuntime();
        sound_.stop();
    });
    restoreTimer_.setSingleShot(true);
    restoreTimer_.setInterval(750);
    connect(&restoreTimer_, &QTimer::timeout, this, [this] {
        if (clock_->isDragging()) {
            scheduleRestore();
            return;
        }
        clock_->restorePosition();
    });
    connect(qApp, &QGuiApplication::screenAdded, this, [this](QScreen *screen) {
        watchScreen(screen);
        scheduleRestore();
    });
    connect(qApp, &QGuiApplication::screenRemoved, this, &ApplicationController::scheduleRestore);
    connect(qApp, &QGuiApplication::primaryScreenChanged, this,
            &ApplicationController::scheduleRestore);
    for (auto *screen : QGuiApplication::screens())
        watchScreen(screen);
    if (clock_->windowHandle())
        connect(clock_->windowHandle(), &QWindow::screenChanged, this,
                &ApplicationController::scheduleRestore);
    connect(&platform_, &PlatformServices::sleeping, this, [this] {
        suppressCountdown_ = true;
        saveRuntime();
    });
    connect(&platform_, &PlatformServices::waking, this, [this] {
        suppressCountdown_ = true;
        tick();
        scheduleRestore();
    });
    previewTimer_.setSingleShot(true);
    previewTimer_.setInterval(3000);
    connect(&previewTimer_, &QTimer::timeout, this, &ApplicationController::stopPreview);
    soundPreviewTimer_.setSingleShot(true);
    soundPreviewTimer_.setInterval(3000);
    connect(&soundPreviewTimer_, &QTimer::timeout, this, [this] {
        if (!reminders_.active())
            sound_.stop();
    });
    if (integration_) {
        platform_.start(clock_.get());
        if (hasTray)
            buildTray();
        else
            panel_->show();
        if (config_.startOnBoot) {
            QString error;
            if (!platform_.setAutostart(true, store_.path(), &error))
                report(error);
        }
    }
    applyClickThrough();
    lastTick_ = lastSample_ = lastSnapshot_ = time_.elapsedNow();
    tick();
    connect(&tickTimer_, &QTimer::timeout, this, &ApplicationController::tick);
    tickTimer_.start(100);
    if (!warning.isEmpty())
        report(warning);
}

ApplicationController::~ApplicationController() {
    tickTimer_.stop();
    sound_.stop();
    if (tray_)
        tray_->hide();
}

void ApplicationController::buildTray() {
    tray_ = new QSystemTrayIcon(QIcon(":/icons/clock.png"), this);
    tray_->setToolTip(QStringLiteral("浮动时钟"));
    menu_ = std::make_unique<QMenu>();
    menu_->addAction(QStringLiteral("控制面板…"), this, &ApplicationController::showControl);
    menu_->addAction(QStringLiteral("设置…"), this, &ApplicationController::openSettings);
    throughAction_ = menu_->addAction(QStringLiteral("鼠标穿透"));
    throughAction_->setCheckable(true);
    throughAction_->setChecked(config_.clickThrough);
    connect(throughAction_, &QAction::toggled, this, [this](bool checked) {
        config_.clickThrough = checked;
        applyClickThrough();
        saveConfig();
    });
    moveAction_ = menu_->addAction(QStringLiteral("移动时钟"));
    moveAction_->setCheckable(true);
    connect(moveAction_, &QAction::toggled, this, &ApplicationController::setMoveMode);
    stopAction_ =
        menu_->addAction(QStringLiteral("停止提醒"), this, &ApplicationController::stopReminders);
    stopAction_->setEnabled(false);
    menu_->addSeparator();
    menu_->addAction(QStringLiteral("退出"), this, &ApplicationController::quit);
    tray_->setContextMenu(menu_.get());
    connect(tray_, &QSystemTrayIcon::activated, this,
            [this](QSystemTrayIcon::ActivationReason reason) {
                if (reason == QSystemTrayIcon::DoubleClick)
                    showControl();
            });
    tray_->show();
}

void ApplicationController::tick() {
    const qint64 now = time_.elapsedNow();
    const bool resumed = suppressCountdown_ || now - lastTick_ > 5000;
    lastTick_ = now;
    suppressCountdown_ = false;
    bool remindersChanged = reminders_.expire(now);
    const bool allowed = config_.ringWhenScreenOff || platform_.displayState() != DisplayState::Off;
    const bool completed = timers_.advance();
    if (completed) {
        if (allowed && !resumed) {
            reminders_.addCountdown(config_, now);
            remindersChanged = true;
        }
        saveRuntime();
    }
    const auto due = scheduler_.check(config_, time_.wallNow(), allowed);
    bool consumed = false;
    for (const auto &alarm : due) {
        reminders_.add(alarm, config_, now);
        remindersChanged = true;
        if (alarm.once()) {
            consumed = true;
            if (settings_)
                settings_->markAlarmFired(alarm);
        }
    }
    if (consumed)
        saveConfig();
    if (remindersChanged)
        syncReminders();
    const QString clockTime = ClockWindow::formattedClock(appearance_, time_.wallNow());
    QString display = clockTime;
    if (timers_.displayMode == "countdown")
        display = Timers::formatDuration(timers_.countdownRemaining());
    else if (timers_.displayMode == "stopwatch")
        display = Timers::formatDuration(timers_.stopwatchElapsed(), true);
    clock_->setDisplay(display, clockTime);
    if (panel_->isVisible())
        panel_->refresh();
    if (now - lastSample_ >= 2000) {
        lastSample_ = now;
        if (integration_) {
            const bool available = QSystemTrayIcon::isSystemTrayAvailable();
            if (available != trayAvailable_) {
                trayAvailable_ = available;
                panel_->setTrayAvailable(available);
                if (available && !tray_)
                    buildTray();
                else if (!available)
                    showControl();
            }
        }
        if (integration_ && platform_.capabilities().screenSampling)
            clock_->sampleBackground();
    }
    if (now - lastSnapshot_ >= 5000 &&
        (timers_.stopwatchRunning() || timers_.countdownState() == Timers::State::Running)) {
        lastSnapshot_ = now;
        saveRuntime();
    }
    const bool fast =
        timers_.stopwatchRunning() && (timers_.displayMode == "stopwatch" || panel_->isVisible());
    const int interval = fast ? 50 : 500;
    if (tickTimer_.interval() != interval)
        tickTimer_.setInterval(interval);
}

void ApplicationController::syncReminders() {
    if (reminders_.active()) {
        previewTimer_.stop();
        previewing_ = false;
        soundPreviewTimer_.stop();
        const auto *sound = reminders_.sound();
        if (sound) {
            if (!reminderSound_ || !(*reminderSound_ == *sound)) {
                Config soundConfig;
                soundConfig.soundMode = sound->mode;
                soundConfig.soundAlias = sound->alias;
                soundConfig.soundPath = sound->path;
                sound_.play(soundConfig);
                reminderSound_ = *sound;
            }
        } else {
            sound_.stop();
            reminderSound_.reset();
        }
        ringing_ = true;
        clock_->setReminder(reminders_.title(), reminders_.content());
        clock_->show();
        clock_->raise();
    } else {
        ringing_ = false;
        reminderSound_.reset();
        sound_.stop();
        clock_->clearReminder();
    }
    if (stopAction_)
        stopAction_->setEnabled(ringing_);
    applyClickThrough();
}

void ApplicationController::stopReminders() {
    stopPreview();
    reminders_.clear();
    syncReminders();
}

void ApplicationController::setMoveMode(bool enabled) {
    moveMode_ = enabled;
    if (moveAction_) {
        const QSignalBlocker block(moveAction_);
        moveAction_->setChecked(enabled);
    }
    clock_->setMoveHint(enabled);
    applyClickThrough();
}

void ApplicationController::applyClickThrough() {
    platform_.setClickThrough(clock_.get(),
                              config_.clickThrough && !moveMode_ && !ringing_ && !previewing_);
}

void ApplicationController::showControl() {
    panel_->refresh();
    panel_->show();
    panel_->raise();
    panel_->activateWindow();
}

void ApplicationController::openSettings() {
    if (settings_) {
        settings_->raise();
        settings_->activateWindow();
        return;
    }
    Config editable = config_;
    if (integration_)
        editable.startOnBoot = platform_.autostartEnabled();
    SettingsDialog dialog(editable, platform_.capabilities(), panel_.get());
    settings_ = &dialog;
    connect(&dialog, &SettingsDialog::previewRequested, this, &ApplicationController::preview);
    connect(&dialog, &SettingsDialog::reminderPreviewRequested, this, [this](const Config &cfg) {
        if (reminders_.active())
            return;
        preview(cfg);
        previewing_ = true;
        clock_->setReminder(QStringLiteral("提醒预览"),
                            QStringLiteral("这是提醒内容预览，3 秒后自动关闭。"));
        applyClickThrough();
        previewTimer_.start();
    });
    connect(&dialog, &SettingsDialog::soundPreviewRequested, this, [this](const Config &cfg) {
        if (reminders_.active())
            return;
        sound_.play(cfg);
        soundPreviewTimer_.start();
    });
    if (dialog.exec() == QDialog::Accepted) {
        Config updated = dialog.resultConfig();
        updated.posX = config_.posX;
        updated.posY = config_.posY;
        if (updated.autoColor && !config_.autoColor && integration_ &&
            !platform_.requestScreenSampling()) {
            updated.autoColor = false;
            report(QStringLiteral("未取得屏幕取色权限，继续使用固定颜色。"));
        }
        QString error;
        if (store_.save(updated, &error)) {
            config_ = updated;
            if (integration_ &&
                !platform_.setAutostart(config_.startOnBoot, store_.path(), &error)) {
                config_.startOnBoot = platform_.autostartEnabled();
                report(error);
                saveConfig();
            }
        } else
            report(error);
    }
    settings_ = nullptr;
    stopPreview();
    soundPreviewTimer_.stop();
    if (!reminders_.active())
        sound_.stop();
    appearance_ = config_;
    clock_->applyConfig(appearance_);
    if (throughAction_) {
        const QSignalBlocker block(throughAction_);
        throughAction_->setChecked(config_.clickThrough);
    }
    applyClickThrough();
    tick();
}

void ApplicationController::preview(const Config &config) {
    appearance_ = config;
    appearance_.posX = config_.posX;
    appearance_.posY = config_.posY;
    clock_->applyConfig(appearance_);
    applyClickThrough();
    tick();
}

void ApplicationController::stopPreview() {
    previewTimer_.stop();
    if (!previewing_)
        return;
    previewing_ = false;
    if (!reminders_.active())
        clock_->clearReminder();
    applyClickThrough();
}

void ApplicationController::watchScreen(QScreen *screen) {
    connect(screen, &QScreen::geometryChanged, this, &ApplicationController::scheduleRestore);
    connect(screen, &QScreen::availableGeometryChanged, this,
            &ApplicationController::scheduleRestore);
    connect(screen, &QScreen::logicalDotsPerInchChanged, this,
            &ApplicationController::scheduleRestore);
}

void ApplicationController::scheduleRestore() {
    restoreTimer_.start();
}

void ApplicationController::saveConfig() {
    QString error;
    if (!store_.save(config_, &error))
        report(error);
}

void ApplicationController::saveRuntime() {
    QString error;
    if (!store_.saveRuntime(timers_.snapshot(), &error))
        report(error);
}

void ApplicationController::report(const QString &message) {
    if (message.isEmpty())
        return;
    panel_->showStatus(message);
    if (message == lastError_)
        return;
    lastError_ = message;
    qWarning().noquote() << message;
    if (tray_)
        tray_->showMessage(QStringLiteral("浮动时钟"), message, QSystemTrayIcon::Warning);
}

void ApplicationController::importConfig() {
    const auto path = QFileDialog::getOpenFileName(panel_.get(), QStringLiteral("导入旧版配置"),
                                                   QString(), QStringLiteral("INI 配置 (*.ini)"),
                                                   nullptr, QFileDialog::DontUseNativeDialog);
    if (path.isEmpty())
        return;
    QString error;
    Config imported;
    if (!store_.importFile(path, &imported, &error)) {
        report(error);
        return;
    }
    config_ = imported;
    if (integration_ && !platform_.setAutostart(config_.startOnBoot, store_.path(), &error)) {
        config_.startOnBoot = platform_.autostartEnabled();
        report(error);
        saveConfig();
    }
    appearance_ = config_;
    clock_->applyConfig(config_);
    if (throughAction_) {
        const QSignalBlocker block(throughAction_);
        throughAction_->setChecked(config_.clickThrough);
    }
    applyClickThrough();
    tick();
    panel_->showStatus(QStringLiteral("配置已导入；原配置已备份，计时进度保持不变。"));
}

void ApplicationController::quit() {
    qApp->quit();
}

Config &ApplicationController::config() {
    return config_;
}

Timers &ApplicationController::timers() {
    return timers_;
}

ClockWindow &ApplicationController::clock() {
    return *clock_;
}

const ReminderController &ApplicationController::reminders() const {
    return reminders_;
}

} // namespace fc
