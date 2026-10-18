#include "core/model.h"

#include <QJsonArray>
#include <QRegularExpression>
#include <QUuid>
#include <algorithm>
#include <cmath>

namespace fc {

bool readBool(const QVariant &raw, bool fallback) {
    if (!raw.isValid() || raw.isNull())
        return fallback;
    const QString text = raw.toString().trimmed().toLower();
    if (text == "true" || text == "yes" || text == "on" || text == "1")
        return true;
    if (text == "false" || text == "no" || text == "off" || text == "0" || text.isEmpty())
        return false;
    return fallback;
}

double readReal(const QVariant &raw, double fallback, double low, double high) {
    bool ok = false;
    const double value = raw.toDouble(&ok);
    return ok && std::isfinite(value) ? std::clamp(value, low, high) : fallback;
}

int readInt(const QVariant &raw, int fallback, int low, int high) {
    return static_cast<int>(readReal(raw, fallback, low, high));
}

Alarm::Alarm() : id(QUuid::createUuid().toString(QUuid::Id128)) {}

bool Alarm::matches(const QDateTime &now) const {
    if (!enabled || time != now.time().toString("HH:mm"))
        return false;
    const int day = now.date().dayOfWeek() - 1;
    return repeat == "once" || repeat == "daily" || (repeat == "weekdays" && day < 5) ||
           (repeat == "custom" && weekdays.contains(day));
}

bool Alarm::once() const {
    return repeat == "once";
}

void Alarm::normalize() {
    if (!QStringList{"once", "daily", "weekdays", "custom"}.contains(repeat))
        repeat = "daily";
    weekdays.erase(std::remove_if(weekdays.begin(), weekdays.end(),
                                  [](int day) { return day < 0 || day > 6; }),
                   weekdays.end());
    std::sort(weekdays.begin(), weekdays.end());
    weekdays.erase(std::unique(weekdays.begin(), weekdays.end()), weekdays.end());
    if (id.trimmed().isEmpty())
        id = QUuid::createUuid().toString(QUuid::Id128);
    if (timeoutSeconds)
        timeoutSeconds = std::clamp(*timeoutSeconds, 1, 3600);
}

QJsonObject Alarm::toJson() const {
    Alarm copy = *this;
    copy.normalize();
    QJsonArray days;
    for (int day : copy.weekdays)
        days.append(day);
    QJsonObject result{{"id", copy.id},           {"time", copy.time},
                       {"label", copy.label},     {"content", copy.content},
                       {"enabled", copy.enabled}, {"repeat_type", copy.repeat},
                       {"repeat_weekdays", days}};
    if (copy.timeoutSeconds)
        result.insert("timeout_seconds", *copy.timeoutSeconds);
    return result;
}

std::optional<Alarm> Alarm::fromJson(const QJsonValue &value) {
    if (!value.isObject())
        return std::nullopt;
    const auto obj = value.toObject();
    Alarm alarm;
    alarm.time = obj.value("time").toString("08:00");
    static const QRegularExpression hhmm(QStringLiteral("^(?:[01][0-9]|2[0-3]):[0-5][0-9]$"));
    if (!hhmm.match(alarm.time).hasMatch())
        return std::nullopt;
    alarm.id = obj.value("id").toString(alarm.id);
    alarm.label = obj.value("label").toString("闹钟");
    alarm.content = obj.value("content").toString();
    alarm.enabled = readBool(obj.value("enabled").toVariant(), true);
    alarm.repeat = obj.value("repeat_type").toString();
    if (alarm.repeat.isEmpty())
        alarm.repeat = readBool(obj.value("repeat_daily").toVariant(), true) ? "daily" : "once";
    for (const auto &day : obj.value("repeat_weekdays").toArray()) {
        const int parsed = readInt(day.toVariant(), -1, -1, 7);
        if (parsed >= 0 && parsed <= 6)
            alarm.weekdays.append(parsed);
    }
    if (obj.contains("timeout_seconds") && !obj.value("timeout_seconds").isNull())
        alarm.timeoutSeconds = readInt(obj.value("timeout_seconds").toVariant(), 60, 1, 3600);
    alarm.normalize();
    return alarm;
}

QVector<Alarm> AlarmScheduler::check(Config &config, const QDateTime &now, bool allowed) {
    if (!allowed || !now.isValid())
        return {};
    // Retain all minutes of the current date so small clock corrections cannot re-ring alarms.
    if (date_ != now.date()) {
        fired_.clear();
        date_ = now.date();
    }
    QVector<Alarm> result;
    for (auto &alarm : config.alarms) {
        const QString key = alarm.id + '/' + now.toString("yyyy-MM-dd HH:mm");
        if (!alarm.matches(now) || fired_.contains(key))
            continue;
        fired_.insert(key);
        result.append(alarm);
        if (alarm.once())
            alarm.enabled = false;
    }
    return result;
}

bool ReminderSound::operator==(const ReminderSound &other) const {
    return mode == other.mode && alias == other.alias && path == other.path;
}

void ReminderController::add(const Alarm &alarm, const Config &config, qint64 now) {
    const int timeout =
        std::clamp(alarm.timeoutSeconds.value_or(config.alarmTimeoutSeconds), 1, 3600);
    items_.append({QUuid::createUuid().toString(QUuid::Id128),
                   alarm.label,
                   alarm.content,
                   now + qint64(timeout) * 1000,
                   {config.soundMode, config.soundAlias, config.soundPath}});
}

void ReminderController::addCountdown(const Config &config, qint64 now) {
    Alarm alarm;
    alarm.label = QStringLiteral("倒计时结束");
    add(alarm, config, now);
}

const ReminderSound *ReminderController::sound() const {
    for (const auto &item : items_)
        if (item.sound.mode != "silent")
            return &item.sound;
    return nullptr;
}

bool ReminderController::expire(qint64 now) {
    const auto before = items_.size();
    items_.erase(std::remove_if(items_.begin(), items_.end(),
                                [now](const Reminder &item) { return now >= item.expiresAt; }),
                 items_.end());
    return before != items_.size();
}

void ReminderController::clear() {
    items_.clear();
}

bool ReminderController::active() const {
    return !items_.isEmpty();
}

const QVector<Reminder> &ReminderController::items() const {
    return items_;
}

QString ReminderController::title() const {
    return items_.size() == 1 ? items_.front().title
                              : QStringLiteral("%1 个提醒").arg(items_.size());
}

QString ReminderController::content() const {
    if (items_.size() == 1)
        return items_.front().content;
    QStringList parts;
    for (const auto &item : items_)
        parts.append(item.title + (item.content.isEmpty() ? QString() : '\n' + item.content));
    return parts.join("\n\n");
}

} // namespace fc
