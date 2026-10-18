#pragma once

#include "core/time_source.h"
#include <QJsonObject>
#include <QVector>

namespace fc {

class Timers {
public:
    enum class State { Idle, Running, Paused, Finished };
    explicit Timers(const TimeSource &time);
    void startCountdown(qint64 durationMs);
    void pauseCountdown();
    void resumeCountdown();
    void resetCountdown();
    // True exactly once when a running countdown completes.
    bool advance();
    qint64 countdownRemaining() const;
    qint64 countdownDuration() const;
    State countdownState() const;
    void startStopwatch();
    void pauseStopwatch();
    void resetStopwatch();
    void lap();
    qint64 stopwatchElapsed() const;
    bool stopwatchRunning() const;
    const QVector<qint64> &laps() const;
    QJsonObject snapshot() const;
    void restore(const QJsonObject &state);
    QString displayMode = QStringLiteral("clock");
    static QString formatDuration(qint64 millis, bool fractions = false);

private:
    const TimeSource &time_;
    State countdownState_ = State::Idle;
    qint64 duration_ = 5 * 60 * 1000;
    qint64 remaining_ = 0;
    qint64 countdownEnd_ = 0;
    bool stopwatchRunning_ = false;
    qint64 stopwatchStart_ = 0;
    qint64 stopwatchAccumulated_ = 0;
    QVector<qint64> laps_;
};

} // namespace fc
