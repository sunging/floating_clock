#include "core/timers.h"

#include <QJsonArray>
#include <algorithm>
#include <cmath>

namespace fc {
namespace {
constexpr qint64 MaxDuration = 99LL * 3600 * 1000 + 59 * 60000 + 59000;
constexpr qint64 MaxElapsed = 3650LL * 24 * 3600 * 1000;
qint64 millis(const QJsonValue &value, qint64 fallback, qint64 maximum = MaxElapsed) {
    const double raw = value.toDouble(static_cast<double>(fallback));
    return std::isfinite(raw) ? static_cast<qint64>(std::clamp(raw, 0.0, double(maximum)))
                              : fallback;
}
} // namespace

Timers::Timers(const TimeSource &time) : time_(time) {}

void Timers::startCountdown(qint64 durationMs) {
    duration_ = std::clamp(durationMs, qint64(1000), MaxDuration);
    remaining_ = duration_;
    countdownEnd_ = time_.elapsedNow() + remaining_;
    countdownState_ = State::Running;
}

void Timers::pauseCountdown() {
    if (countdownState_ != State::Running)
        return;
    remaining_ = countdownRemaining();
    countdownState_ = remaining_ ? State::Paused : State::Finished;
}

void Timers::resumeCountdown() {
    if (countdownState_ != State::Paused)
        return;
    countdownEnd_ = time_.elapsedNow() + remaining_;
    countdownState_ = State::Running;
}

void Timers::resetCountdown() {
    countdownState_ = State::Idle;
    remaining_ = 0;
}

bool Timers::advance() {
    if (countdownState_ == State::Running && countdownRemaining() == 0) {
        countdownState_ = State::Finished;
        remaining_ = 0;
        return true;
    }
    return false;
}

qint64 Timers::countdownRemaining() const {
    if (countdownState_ == State::Running)
        return std::max(qint64(0), countdownEnd_ - time_.elapsedNow());
    return countdownState_ == State::Idle ? duration_ : remaining_;
}

qint64 Timers::countdownDuration() const {
    return duration_;
}

Timers::State Timers::countdownState() const {
    return countdownState_;
}

void Timers::startStopwatch() {
    if (stopwatchRunning_)
        return;
    stopwatchStart_ = time_.elapsedNow();
    stopwatchRunning_ = true;
}

void Timers::pauseStopwatch() {
    stopwatchAccumulated_ = stopwatchElapsed();
    stopwatchRunning_ = false;
}

void Timers::resetStopwatch() {
    stopwatchRunning_ = false;
    stopwatchAccumulated_ = 0;
    laps_.clear();
}

void Timers::lap() {
    if (stopwatchRunning_ && laps_.size() < 10000)
        laps_.append(stopwatchElapsed());
}

qint64 Timers::stopwatchElapsed() const {
    return stopwatchAccumulated_ +
           (stopwatchRunning_ ? std::max(qint64(0), time_.elapsedNow() - stopwatchStart_) : 0);
}

bool Timers::stopwatchRunning() const {
    return stopwatchRunning_;
}

const QVector<qint64> &Timers::laps() const {
    return laps_;
}

QJsonObject Timers::snapshot() const {
    QJsonArray laps;
    for (qint64 lap : laps_)
        laps.append(lap);
    const qint64 remaining = countdownRemaining();
    return {{"schema_version", 1},
            {"display_mode", displayMode},
            {"countdown_state", static_cast<int>(countdownState_)},
            {"countdown_duration_ms", duration_},
            {"countdown_remaining_ms", remaining},
            {"countdown_end_utc_ms", time_.wallNow().toMSecsSinceEpoch() + remaining},
            {"stopwatch_elapsed_ms", stopwatchElapsed()},
            {"laps_ms", laps}};
}

void Timers::restore(const QJsonObject &state) {
    resetCountdown();
    resetStopwatch();
    displayMode = state.value("display_mode").toString("clock");
    if (!QStringList{"clock", "countdown", "stopwatch"}.contains(displayMode))
        displayMode = "clock";
    duration_ = std::clamp(millis(state.value("countdown_duration_ms"), 300000, MaxDuration),
                           qint64(1000), MaxDuration);
    remaining_ = millis(state.value("countdown_remaining_ms"), 0, duration_);
    const int saved = state.value("countdown_state").toInt(0);
    if (saved == static_cast<int>(State::Paused))
        countdownState_ = remaining_ ? State::Paused : State::Finished;
    else if (saved == static_cast<int>(State::Finished)) {
        countdownState_ = State::Finished;
        remaining_ = 0;
    } else if (saved == static_cast<int>(State::Running)) {
        const qint64 end = millis(state.value("countdown_end_utc_ms"), 0, 8640000000000000LL);
        remaining_ = std::clamp(end - time_.wallNow().toMSecsSinceEpoch(), qint64(0), duration_);
        countdownState_ = remaining_ ? State::Running : State::Finished;
        countdownEnd_ = time_.elapsedNow() + remaining_;
    }
    stopwatchAccumulated_ = millis(state.value("stopwatch_elapsed_ms"), 0);
    qint64 previous = 0;
    for (const auto &value : state.value("laps_ms").toArray()) {
        const qint64 lap = millis(value, 0, stopwatchAccumulated_);
        if (lap >= previous && laps_.size() < 10000) {
            laps_.append(lap);
            previous = lap;
        }
    }
}

QString Timers::formatDuration(qint64 millis, bool fractions) {
    millis = std::max(qint64(0), millis);
    const qint64 seconds = fractions ? millis / 1000 : (millis + 999) / 1000;
    QString text = QStringLiteral("%1:%2:%3")
                       .arg(seconds / 3600, 2, 10, QLatin1Char('0'))
                       .arg((seconds / 60) % 60, 2, 10, QLatin1Char('0'))
                       .arg(seconds % 60, 2, 10, QLatin1Char('0'));
    if (fractions)
        text += QStringLiteral(".%1").arg((millis % 1000) / 10, 2, 10, QLatin1Char('0'));
    return text;
}

} // namespace fc
