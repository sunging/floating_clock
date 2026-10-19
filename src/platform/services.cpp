#include "platform/services.h"
#include "core/i18n.h"

#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QGuiApplication>
#include <QPixmap>
#include <QSaveFile>
#include <QScreen>
#include <QSettings>
#include <QStandardPaths>
#include <QUrl>

#if defined(Q_OS_WIN)
#define WIN32_LEAN_AND_MEAN
// clang-format off
// Windows types must be declared before the multimedia API headers.
#include <windows.h>
#include <mmsystem.h>
// clang-format on
#elif defined(Q_OS_LINUX)
#include <QDBusConnection>
#include <X11/Xlib.h>
#include <X11/extensions/dpms.h>
#endif

namespace fc {
namespace {
#ifdef Q_OS_WIN
const QString RunKey =
    QStringLiteral("HKEY_CURRENT_USER\\Software\\Microsoft\\Windows\\CurrentVersion\\Run");

class WindowsWavePlayer final : public WavePlayer {
public:
    bool playAlias(const QString &alias) override {
        return play(reinterpret_cast<LPCWSTR>(alias.utf16()), SND_ALIAS);
    }
    bool playFile(const QString &path) override {
        return play(reinterpret_cast<LPCWSTR>(path.utf16()), SND_FILENAME);
    }
    bool playMemory(const QByteArray &wave) override {
        // PlaySound reads asynchronously, so the buffer must live until stop() returns.
        wave_ = wave;
        return play(reinterpret_cast<LPCWSTR>(wave_.constData()), SND_MEMORY);
    }
    void stop() override {
        if (playing_)
            PlaySoundW(nullptr, nullptr, 0);
        playing_ = false;
        wave_.clear();
    }

private:
    bool play(LPCWSTR source, DWORD type) {
        playing_ = PlaySoundW(source, nullptr, type | SND_ASYNC | SND_LOOP | SND_NODEFAULT);
        return playing_;
    }
    QByteArray wave_;
    bool playing_ = false;
};
#endif

#ifdef Q_OS_LINUX
QString desktopFile() {
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) +
           "/autostart/floating-clock.desktop";
}

QString desktopQuote(QString value) {
    value.replace('\\', "\\\\");
    value.replace('"', "\\\"");
    value.replace('`', "\\`");
    value.replace('$', "\\$");
    value.replace('%', "%%");
    value.replace('\n', "\\n");
    return '"' + value + '"';
}
#endif
} // namespace

QImage captureScreenRegion(const QRect &geometry) {
    if (QGuiApplication::platformName().startsWith("wayland"))
        return {};
    auto *screen = QGuiApplication::screenAt(geometry.center());
    if (!screen)
        screen = QGuiApplication::primaryScreen();
    if (!screen)
        return {};
    const auto pixmap = screen->grabWindow(0);
    if (pixmap.isNull())
        return {};
    const qreal dpr = pixmap.devicePixelRatio();
    const QRect local =
        geometry.intersected(screen->geometry()).translated(-screen->geometry().topLeft());
    const QRect pixels(qRound(local.x() * dpr), qRound(local.y() * dpr),
                       qRound(local.width() * dpr), qRound(local.height() * dpr));
    const auto captured = pixels.intersected(pixmap.rect());
    return captured.isEmpty() ? QImage() : pixmap.copy(captured).toImage();
}

PlatformServices::PlatformServices(QObject *parent) : QObject(parent) {
    const auto backend = QGuiApplication::platformName();
    if (backend.startsWith("wayland")) {
        capabilities_.positioning = false;
        capabilities_.screenSampling = false;
        capabilities_.explanation = QString::fromUtf8(QT_TRANSLATE_NOOP(
            "FloatingClock", "Wayland controls window positioning and stacking. Reliable position "
                             "restoration, continuous background sampling and display-power "
                             "detection are unavailable. Unknown display power is treated as on."));
    }
    if (backend == "offscreen" || backend == "minimal") {
        capabilities_.clickThrough = false;
        capabilities_.positioning = false;
        capabilities_.screenSampling = false;
    }
}

PlatformServices::~PlatformServices() {
    QCoreApplication::instance()->removeNativeEventFilter(this);
#ifdef Q_OS_WIN
    if (nativeHandle_)
        UnregisterPowerSettingNotification(static_cast<HPOWERNOTIFY>(nativeHandle_));
#elif defined(Q_OS_LINUX)
    if (nativeHandle_)
        XCloseDisplay(static_cast<Display *>(nativeHandle_));
#endif
}

void PlatformServices::start(QWidget *window) {
    QCoreApplication::instance()->installNativeEventFilter(this);
#ifdef Q_OS_WIN
    static const GUID displayGuid = {
        0x6fe69556, 0x704a, 0x47a0, {0x8f, 0x24, 0xc2, 0x8d, 0x93, 0x6f, 0xda, 0x47}};
    nativeHandle_ = RegisterPowerSettingNotification(reinterpret_cast<HWND>(window->winId()),
                                                     &displayGuid, DEVICE_NOTIFY_WINDOW_HANDLE);
    capabilities_.displayPower = nativeHandle_ != nullptr;
#elif defined(Q_OS_LINUX)
    Q_UNUSED(window)
    QDBusConnection::systemBus().connect("org.freedesktop.login1", "/org/freedesktop/login1",
                                         "org.freedesktop.login1.Manager", "PrepareForSleep", this,
                                         SLOT(handleSleep(bool)));
    if (QGuiApplication::platformName() == "xcb" && qEnvironmentVariableIsEmpty("WAYLAND_DISPLAY"))
        nativeHandle_ = XOpenDisplay(nullptr);
    if (nativeHandle_ && DPMSCapable(static_cast<Display *>(nativeHandle_))) {
        capabilities_.displayPower = true;
        connect(&poll_, &QTimer::timeout, this, [this] {
            CARD16 level = DPMSModeOn;
            BOOL enabled = false;
            if (!DPMSInfo(static_cast<Display *>(nativeHandle_), &level, &enabled)) {
                displayState_ = DisplayState::Unknown;
                return;
            }
            const auto old = displayState_;
            displayState_ = enabled && level != DPMSModeOn ? DisplayState::Off : DisplayState::On;
            if (old == DisplayState::Off && displayState_ == DisplayState::On)
                emit waking();
        });
        poll_.start(1000);
    }
#else
    Q_UNUSED(window)
#endif
}

Capabilities PlatformServices::capabilities() const {
    return capabilities_;
}

DisplayState PlatformServices::displayState() const {
    return displayState_;
}

void PlatformServices::setClickThrough(QWidget *window, bool enabled) {
    if (!capabilities_.clickThrough)
        return;
#ifdef Q_OS_WIN
    const auto hwnd = reinterpret_cast<HWND>(window->winId());
    LONG_PTR style = GetWindowLongPtrW(hwnd, GWL_EXSTYLE);
    style = enabled ? style | WS_EX_TRANSPARENT : style & ~LONG_PTR(WS_EX_TRANSPARENT);
    SetWindowLongPtrW(hwnd, GWL_EXSTYLE, style);
#else
    const bool visible = window->isVisible();
    window->setWindowFlag(Qt::WindowTransparentForInput, enabled);
    if (visible)
        window->show();
#endif
}

bool PlatformServices::setAutostart(bool enabled, const QString &configPath, QString *error) {
#ifdef Q_OS_WIN
    QSettings settings(RunKey, QSettings::NativeFormat);
    if (enabled) {
        const QString exe = QDir::toNativeSeparators(QCoreApplication::applicationFilePath());
        settings.setValue("FloatingClock",
                          QStringLiteral("\"%1\" --config \"%2\"").arg(exe, configPath));
    } else
        settings.remove("FloatingClock");
    settings.sync();
    if (settings.status() == QSettings::NoError)
        return true;
#elif defined(Q_OS_LINUX)
    const QString path = desktopFile();
    if (!enabled) {
        if (!QFileInfo::exists(path) || QFile::remove(path))
            return true;
        if (error)
            *error =
                I18n::tr("Could not remove the autostart file. Check user-directory permissions.");
        return false;
    }
    QString executable = qEnvironmentVariable("APPIMAGE");
    if (executable.isEmpty())
        executable = QCoreApplication::applicationFilePath();
    const QByteArray content =
        QStringLiteral(
            "[Desktop Entry]\nType=Application\nName=Floating Clock\nName[zh_CN]=浮动时钟\nExec=%1 "
            "--config %2\nTerminal=false\nX-GNOME-Autostart-enabled=true\n")
            .arg(desktopQuote(executable), desktopQuote(configPath))
            .toUtf8();
    QSaveFile file(path);
    if (QDir().mkpath(QFileInfo(path).absolutePath()) && file.open(QIODevice::WriteOnly) &&
        file.write(content) == content.size() && file.commit())
        return true;
#else
    Q_UNUSED(enabled)
    Q_UNUSED(configPath)
#endif
    if (error)
        *error = I18n::tr(
            "Could not change autostart settings. Check user-directory or system permissions.");
    return false;
}

bool PlatformServices::autostartEnabled() const {
#ifdef Q_OS_WIN
    return !QSettings(RunKey, QSettings::NativeFormat).value("FloatingClock").toString().isEmpty();
#elif defined(Q_OS_LINUX)
    return QFileInfo::exists(desktopFile());
#else
    return false;
#endif
}

bool PlatformServices::requestScreenSampling() {
    return capabilities_.screenSampling;
}

QImage PlatformServices::sampleBackground(const QRect &geometry) const {
    return capabilities_.screenSampling ? captureScreenRegion(geometry) : QImage();
}

void PlatformServices::handleSleep(bool asleep) {
    if (asleep)
        emit sleeping();
    else
        emit waking();
}

bool PlatformServices::nativeEventFilter(const QByteArray &eventType, void *message,
                                         qintptr *result) {
    Q_UNUSED(result)
#ifdef Q_OS_WIN
    if (eventType != "windows_generic_MSG" && eventType != "windows_dispatcher_MSG")
        return false;
    const auto *msg = static_cast<MSG *>(message);
    if (msg->message != WM_POWERBROADCAST)
        return false;
    if (msg->wParam == PBT_APMSUSPEND)
        emit sleeping();
    else if (msg->wParam == PBT_APMRESUMEAUTOMATIC || msg->wParam == PBT_APMRESUMESUSPEND)
        emit waking();
    else if (msg->wParam == PBT_POWERSETTINGCHANGE && msg->lParam) {
        static const GUID displayGuid = {
            0x6fe69556, 0x704a, 0x47a0, {0x8f, 0x24, 0xc2, 0x8d, 0x93, 0x6f, 0xda, 0x47}};
        const auto *setting = reinterpret_cast<POWERBROADCAST_SETTING *>(msg->lParam);
        if (IsEqualGUID(setting->PowerSetting, displayGuid) &&
            setting->DataLength >= sizeof(DWORD)) {
            const bool wasOff = displayState_ == DisplayState::Off;
            displayState_ = setting->Data[0] == 0 ? DisplayState::Off : DisplayState::On;
            if (wasOff && displayState_ == DisplayState::On)
                emit waking();
        }
    }
#else
    Q_UNUSED(eventType)
    Q_UNUSED(message)
#endif
    return false;
}

#ifndef Q_OS_MACOS
std::unique_ptr<PlatformServices> makePlatformServices() {
    return std::make_unique<PlatformServices>();
}
#endif

SoundService::SoundService(QObject *parent) : QObject(parent) {}

#ifdef Q_OS_WIN
SoundService::SoundService(std::unique_ptr<WavePlayer> player, QObject *parent)
    : QObject(parent), player_(std::move(player)) {}
#else
void SoundService::ensureEffect() {
    if (effect_)
        return;
    effect_ = std::make_unique<QSoundEffect>();
    effect_->setLoopCount(QSoundEffect::Infinite);
    connect(effect_.get(), &QSoundEffect::statusChanged, this, [this] {
        if (!wanted_)
            return;
        if (effect_->status() == QSoundEffect::Error) {
            if (!fallback_) {
                fallback_ = true;
                effect_->setSource(QUrl("qrc:/sounds/chime.wav"));
                effect_->play();
                emit failed(I18n::tr("Could not play the custom sound. Using the built-in sound."));
            } else {
                wanted_ = false;
                emit failed(
                    I18n::tr("The audio device is unavailable. Visual reminders remain active."));
            }
        }
    });
}
#endif

SoundService::~SoundService() {
    stop();
}

void SoundService::play(const Config &config) {
    stop();
    if (config.soundMode == "silent")
        return;
#ifdef Q_OS_WIN
    if (!player_)
        player_ = std::make_unique<WindowsWavePlayer>();
    if (config.soundMode == "system" && player_->playAlias(config.soundAlias))
        return;
    if (config.soundMode == "custom") {
        if (QFileInfo::exists(config.soundPath) && player_->playFile(config.soundPath))
            return;
        emit failed(I18n::tr(
            "The custom sound is missing or could not be played. Using the built-in sound."));
    }
    QFile wave(":/sounds/chime.wav");
    if (!wave.open(QIODevice::ReadOnly) || !player_->playMemory(wave.readAll()))
        emit failed(I18n::tr("The audio device is unavailable. Visual reminders remain active."));
#else
    ensureEffect();
    wanted_ = true;
    fallback_ = config.soundMode != "custom" || !QFileInfo::exists(config.soundPath);
    if (config.soundMode == "custom" && fallback_)
        emit failed(I18n::tr("The custom sound is missing. Using the built-in sound."));
    effect_->setSource(fallback_ ? QUrl("qrc:/sounds/chime.wav")
                                 : QUrl::fromLocalFile(config.soundPath));
    effect_->play();
#endif
}

void SoundService::stop() {
#ifdef Q_OS_WIN
    if (player_)
        player_->stop();
#else
    wanted_ = false;
    if (effect_)
        effect_->stop();
#endif
}

} // namespace fc
