#pragma once

#include "core/model.h"
#include <QAbstractNativeEventFilter>
#include <QImage>
#include <QObject>
#include <QTimer>
#include <QWidget>
#include <memory>
#ifndef Q_OS_WIN
#include <QSoundEffect>
#endif

namespace fc {

QImage captureScreenRegion(const QRect &geometry);

enum class DisplayState { Unknown, On, Off };
struct Capabilities {
    bool clickThrough = true;
    bool positioning = true;
    bool screenSampling = true;
    bool displayPower = false;
    QString explanation;
};

class PlatformServices : public QObject, public QAbstractNativeEventFilter {
    Q_OBJECT
public:
    explicit PlatformServices(QObject *parent = nullptr);
    ~PlatformServices() override;
    virtual void start(QWidget *window);
    virtual Capabilities capabilities() const;
    virtual DisplayState displayState() const;
    virtual void setClickThrough(QWidget *window, bool enabled);
    virtual bool setAutostart(bool enabled, const QString &configPath, QString *error);
    virtual bool autostartEnabled() const;
    virtual bool requestScreenSampling();
    virtual QImage sampleBackground(const QRect &geometry) const;
    bool nativeEventFilter(const QByteArray &eventType, void *message, qintptr *result) override;

signals:
    void waking();
    void sleeping();

protected slots:
    void handleSleep(bool sleeping);

protected:
    DisplayState displayState_ = DisplayState::Unknown;
    Capabilities capabilities_;

private:
#if defined(Q_OS_WIN) || defined(Q_OS_LINUX)
    void *nativeHandle_ = nullptr;
#endif
    QTimer poll_;
};

std::unique_ptr<PlatformServices> makePlatformServices();

#ifdef Q_OS_WIN
// This seam keeps native WAV playback testable without touching an audio device.
class WavePlayer {
public:
    virtual ~WavePlayer() = default;
    virtual bool playAlias(const QString &alias) = 0;
    virtual bool playFile(const QString &path) = 0;
    virtual bool playMemory(const QByteArray &wave) = 0;
    virtual void stop() = 0;
};
#endif

class SoundService : public QObject {
    Q_OBJECT
public:
    explicit SoundService(QObject *parent = nullptr);
#ifdef Q_OS_WIN
    explicit SoundService(std::unique_ptr<WavePlayer> player, QObject *parent = nullptr);
#endif
    ~SoundService() override;
    virtual void play(const Config &config);
    virtual void stop();

signals:
    void failed(const QString &message);

private:
#ifdef Q_OS_WIN
    std::unique_ptr<WavePlayer> player_;
#else
    void ensureEffect();
    std::unique_ptr<QSoundEffect> effect_;
    bool fallback_ = false;
    bool wanted_ = false;
#endif
};

} // namespace fc
