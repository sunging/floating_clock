#pragma once

#include "core/model.h"
#include <QJsonObject>

namespace fc {

class ConfigStore {
public:
    explicit ConfigStore(QString path);
    Config load(QString *warning = nullptr) const;
    bool save(const Config &config, QString *error = nullptr) const;
    bool importFile(const QString &source, Config *result, QString *error = nullptr) const;
    QJsonObject loadRuntime(QString *warning = nullptr) const;
    bool saveRuntime(const QJsonObject &state, QString *error = nullptr) const;
    QString path() const;
    QString runtimePath() const;
    static QString defaultPath();
    static QStringList scalarKeys();

private:
    bool backup(QString *error) const;
    QString path_;
};

} // namespace fc
