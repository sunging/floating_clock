#include "core/config_store.h"

#include <QColor>
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QJsonArray>
#include <QJsonDocument>
#include <QSaveFile>
#include <QSettings>
#include <QStandardPaths>
#include <QUuid>
#include <cmath>
#include <functional>
#include <limits>

namespace fc {
namespace {
constexpr int Schema = 2;
constexpr qint64 MaxConfigBytes = 8 * 1024 * 1024;
struct Field {
    QString key;
    std::function<QVariant(const Config &)> get;
    std::function<void(Config &, const QVariant &)> set;
};

QString color(const QVariant &raw, const QString &fallback) {
    QColor value(raw.toString());
    return value.isValid() ? value.name() : fallback;
}

QString choice(const QVariant &raw, const QString &fallback, const QStringList &choices) {
    return choices.contains(raw.toString()) ? raw.toString() : fallback;
}

std::optional<int> position(const QVariant &raw) {
    bool ok = false;
    const double value = raw.toDouble(&ok);
    if (!ok || !std::isfinite(value) || value < std::numeric_limits<int>::min() ||
        value > std::numeric_limits<int>::max())
        return std::nullopt;
    return static_cast<int>(value);
}

// The field table is shared by readers, writers and schema coverage tests.
#define FIELD(key, member, read)                                                                   \
    {key, [](const Config &cfg) -> QVariant { return cfg.member; },                                \
     [](Config &cfg, const QVariant &raw) { cfg.member = (read); }}
#define BOOL(key, member) FIELD(key, member, readBool(raw, Config().member))
#define COLOR(key, member) FIELD(key, member, color(raw, Config().member))
const QVector<Field> &fields() {
    static const QVector<Field> result{
        FIELD("font_size", fontSize, readInt(raw, 48, 8, 400)),
        FIELD("opacity", opacity, readReal(raw, 0.75, 0.1, 1.0)),
        COLOR("color", color),
        BOOL("auto_color", autoColor),
        COLOR("auto_color_dark_bg", darkBackgroundColor),
        COLOR("auto_color_light_bg", lightBackgroundColor),
        BOOL("show_seconds", showSeconds),
        BOOL("show_date", showDate),
        BOOL("click_through", clickThrough),
        BOOL("start_on_boot", startOnBoot),
        FIELD("sound_mode", soundMode, choice(raw, "system", {"silent", "system", "custom"})),
        FIELD("sound_system_alias", soundAlias, raw.toString()),
        FIELD("sound_custom_path", soundPath, raw.toString()),
        BOOL("ring_when_screen_off", ringWhenScreenOff),
        COLOR("alarm_popup_text_color", popupTextColor),
        COLOR("alarm_popup_background_color", popupBackgroundColor),
        FIELD("alarm_popup_background_opacity", popupOpacity, readReal(raw, 0.65, 0.0, 1.0)),
        BOOL("alarm_popup_flash_enabled", popupFlash),
        FIELD("alarm_popup_font_scale", popupFontScale, readReal(raw, 1.0, 0.5, 3.0)),
        FIELD("alarm_popup_layout", popupLayout,
              choice(raw, "label_time", {"label_time", "time_label", "label_only"})),
        FIELD("alarm_timeout_seconds", alarmTimeoutSeconds, readInt(raw, 60, 1, 3600)),
        {"pos_x", [](const Config &cfg) { return cfg.posX ? QVariant(*cfg.posX) : QVariant(""); },
         [](Config &cfg, const QVariant &raw) { cfg.posX = position(raw); }},
        {"pos_y", [](const Config &cfg) { return cfg.posY ? QVariant(*cfg.posY) : QVariant(""); },
         [](Config &cfg, const QVariant &raw) { cfg.posY = position(raw); }},
    };
    return result;
}
#undef FIELD
#undef BOOL
#undef COLOR

bool fail(QString *error, const QString &message) {
    if (error)
        *error = message;
    return false;
}

void warn(QString *warning, const QString &message) {
    if (warning) {
        if (!warning->isEmpty())
            *warning += '\n';
        *warning += message;
    }
}

bool ensureParent(const QString &path, QString *error) {
    return QDir().mkpath(QFileInfo(path).absolutePath()) ||
           fail(error, QStringLiteral("无法创建配置目录：%1").arg(QFileInfo(path).absolutePath()));
}
} // namespace

ConfigStore::ConfigStore(QString path) : path_(QFileInfo(path).absoluteFilePath()) {}

Config ConfigStore::load(QString *warning) const {
    if (warning)
        warning->clear();
    Config result;
    if (QFileInfo(path_).size() > MaxConfigBytes) {
        warn(warning, QStringLiteral("配置文件过大，已使用默认设置。"));
        return result;
    }
    QSettings settings(path_, QSettings::IniFormat);
    for (const auto &field : fields())
        field.set(result, settings.value(field.key, field.get(result)));
    QJsonParseError parseError;
    const auto doc =
        QJsonDocument::fromJson(settings.value("alarms", "[]").toString().toUtf8(), &parseError);
    if (parseError.error != QJsonParseError::NoError || !doc.isArray())
        warn(warning, QStringLiteral("闹钟列表损坏，已跳过；再次保存前会备份原文件。"));
    else {
        QSet<QString> ids;
        bool skipped = false;
        for (const auto &entry : doc.array()) {
            auto alarm = Alarm::fromJson(entry);
            if (!alarm) {
                skipped = true;
                continue;
            }
            if (ids.contains(alarm->id))
                alarm->id = QUuid::createUuid().toString(QUuid::Id128);
            ids.insert(alarm->id);
            result.alarms.append(*alarm);
        }
        if (skipped)
            warn(warning, QStringLiteral("已跳过无效的闹钟条目，其余闹钟正常载入。"));
    }
    if (settings.status() != QSettings::NoError)
        warn(warning, QStringLiteral("读取配置失败或格式损坏：%1").arg(path_));
    if (settings.value("schema_version", 0).toInt() > Schema)
        warn(warning, QStringLiteral("此配置由更新版本创建，保存已禁用，请升级应用。"));
    return result;
}

bool ConfigStore::backup(QString *error) const {
    if (!QFileInfo::exists(path_))
        return true;
    const QString destination = path_ + '.' +
                                QDateTime::currentDateTimeUtc().toString("yyyyMMdd-HHmmss-zzz") +
                                '.' + QUuid::createUuid().toString(QUuid::Id128).left(8) + ".bak";
    return QFile::copy(path_, destination) ||
           fail(error, QStringLiteral("无法备份原配置，已取消写入：%1").arg(path_));
}

bool ConfigStore::save(const Config &config, QString *error) const {
    if (!ensureParent(path_, error))
        return false;
    QSettings settings(path_, QSettings::IniFormat);
    settings.setAtomicSyncRequired(true);
    const int schema = settings.value("schema_version", 0).toInt();
    if (schema > Schema)
        return fail(error, QStringLiteral("配置版本较新，不能覆盖，请升级应用。"));
    QString existingWarning;
    load(&existingWarning);
    if ((schema < Schema || !existingWarning.isEmpty()) && !backup(error))
        return false;
    Config normalized;
    for (const auto &field : fields()) {
        field.set(normalized, field.get(config));
        settings.setValue(field.key, field.get(normalized));
    }
    QJsonArray alarms;
    for (const auto &alarm : config.alarms)
        alarms.append(alarm.toJson());
    settings.setValue("alarms",
                      QString::fromUtf8(QJsonDocument(alarms).toJson(QJsonDocument::Compact)));
    settings.setValue("schema_version", Schema);
    settings.sync();
    return settings.status() == QSettings::NoError ||
           fail(error, QStringLiteral("保存失败，请检查目录权限和剩余空间：%1").arg(path_));
}

bool ConfigStore::importFile(const QString &source, Config *result, QString *error) const {
    if (!QFileInfo::exists(source) || !QFileInfo(source).isReadable())
        return fail(error, QStringLiteral("无法读取导入文件。"));
    QString warning;
    const Config imported = ConfigStore(source).load(&warning);
    if (!warning.isEmpty())
        return fail(error, QStringLiteral("导入未完成：%1").arg(warning));
    if (!backup(error) || !save(imported, error))
        return false;
    if (result)
        *result = imported;
    return true;
}

QJsonObject ConfigStore::loadRuntime(QString *warning) const {
    QFile file(runtimePath());
    if (!file.exists())
        return {};
    if (!file.open(QIODevice::ReadOnly) || file.size() > MaxConfigBytes) {
        warn(warning, QStringLiteral("无法读取计时状态。"));
        return {};
    }
    const auto doc = QJsonDocument::fromJson(file.readAll());
    if (doc.isObject() && doc.object().value("schema_version").toInt() > 1) {
        warn(warning, QStringLiteral("计时状态由更新版本创建，保存已禁用，请升级应用。"));
        return {};
    }
    if (!doc.isObject() || doc.object().value("schema_version").toInt() != 1) {
        warn(warning, QStringLiteral("计时状态损坏或版本不兼容，已重置计时。"));
        return {};
    }
    return doc.object();
}

bool ConfigStore::saveRuntime(const QJsonObject &state, QString *error) const {
    if (!ensureParent(runtimePath(), error))
        return false;
    QFile previous(runtimePath());
    if (previous.exists()) {
        if (!previous.open(QIODevice::ReadOnly) || previous.size() > MaxConfigBytes)
            return fail(error, QStringLiteral("无法检查原计时状态，已取消覆盖。"));
        const auto doc = QJsonDocument::fromJson(previous.readAll());
        if (doc.isObject() && doc.object().value("schema_version").toInt() > 1)
            return fail(error, QStringLiteral("计时状态版本较新，不能覆盖，请升级应用。"));
        previous.close();
    }
    QSaveFile file(runtimePath());
    const auto bytes = QJsonDocument(state).toJson();
    if (!file.open(QIODevice::WriteOnly) || file.write(bytes) != bytes.size() || !file.commit())
        return fail(error, QStringLiteral("无法保存计时状态：%1").arg(file.errorString()));
    return true;
}

QString ConfigStore::path() const {
    return path_;
}

QString ConfigStore::runtimePath() const {
    return QFileInfo(path_).absolutePath() + "/state.json";
}

QString ConfigStore::defaultPath() {
    const auto executableDir = QCoreApplication::applicationDirPath();
    if (QFileInfo::exists(executableDir + "/portable.flag"))
        return executableDir + "/config/config.ini";
#if defined(Q_OS_WIN)
    QString base = qEnvironmentVariable("APPDATA");
    if (base.isEmpty())
        base = QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation);
    return base + "/FloatingClock/config/config.ini";
#elif defined(Q_OS_MACOS)
    return QStandardPaths::writableLocation(QStandardPaths::GenericDataLocation) +
           "/FloatingClock/config/config.ini";
#else
    return QStandardPaths::writableLocation(QStandardPaths::GenericConfigLocation) +
           "/floating_clock/config/config.ini";
#endif
}

QStringList ConfigStore::scalarKeys() {
    QStringList keys;
    for (const auto &field : fields())
        keys.append(field.key);
    return keys;
}

} // namespace fc
