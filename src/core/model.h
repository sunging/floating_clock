#pragma once

#include <QDateTime>
#include <QJsonObject>
#include <QSet>
#include <QString>
#include <QVariant>
#include <QVector>
#include <optional>

namespace fc {

bool readBool(const QVariant &raw, bool fallback = false);
int readInt(const QVariant &raw, int fallback, int low, int high);
double readReal(const QVariant &raw, double fallback, double low, double high);

struct Alarm {
    QString id;
    QString time = QStringLiteral("08:00");
    QString label;
    QString content;
    bool enabled = true;
    QString repeat = QStringLiteral("daily");
    QVector<int> weekdays;
    std::optional<int> timeoutSeconds;

    Alarm();
    bool matches(const QDateTime &now) const;
    bool once() const;
    void normalize();
    QJsonObject toJson() const;
    static std::optional<Alarm> fromJson(const QJsonValue &value);
};

struct Config {
    QString language = QStringLiteral("system");
    int fontSize = 48;
    double opacity = 0.75;
    QString color = QStringLiteral("#FFFFFF");
    bool autoColor = false;
    QString darkBackgroundColor = QStringLiteral("#F0F0F0");
    QString lightBackgroundColor = QStringLiteral("#202020");
    bool showSeconds = true;
    bool showDate = false;
    bool clickThrough = true;
    bool startOnBoot = false;
    QString soundMode = QStringLiteral("system");
    QString soundAlias = QStringLiteral("SystemHand");
    QString soundPath;
    bool ringWhenScreenOff = false;
    std::optional<int> posX;
    std::optional<int> posY;
    QString popupTextColor = QStringLiteral("#FF3030");
    QString popupBackgroundColor = QStringLiteral("#202020");
    double popupOpacity = 0.65;
    bool popupFlash = true;
    double popupFontScale = 1.0;
    QString popupLayout = QStringLiteral("label_time");
    int alarmTimeoutSeconds = 60;
    QVector<Alarm> alarms;
};

// Keep scheduling independent of the GUI and of any real wall clock.
class AlarmScheduler {
public:
    QVector<Alarm> check(Config &config, const QDateTime &now, bool allowed);

private:
    QSet<QString> fired_;
    QDate date_;
};

struct ReminderSound {
    QString mode;
    QString alias;
    QString path;
    bool operator==(const ReminderSound &other) const;
};

struct Reminder {
    QString id;
    QString title;
    QString content;
    qint64 expiresAt = 0;
    ReminderSound sound;
    bool countdown = false;
    QString displayTitle() const;
};

class ReminderController {
public:
    void add(const Alarm &alarm, const Config &config, qint64 now);
    void addCountdown(const Config &config, qint64 now);
    bool expire(qint64 now);
    void clear();
    bool active() const;
    const QVector<Reminder> &items() const;
    const ReminderSound *sound() const;
    QString title() const;
    QString content() const;

private:
    QVector<Reminder> items_;
};

} // namespace fc
