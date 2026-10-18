#pragma once

#include <QLocalServer>
#include <QLockFile>
#include <QObject>
#include <memory>

namespace fc {

class SingleInstance : public QObject {
    Q_OBJECT
public:
    enum class Result { Primary, ActivatedExisting, Error };
    explicit SingleInstance(const QString &configPath, QObject *parent = nullptr);
    Result start(QString *error);
    QString name() const;

signals:
    void activated();

private:
    QString directory_;
    QString name_;
    std::unique_ptr<QLockFile> lock_;
    QLocalServer server_;
};

} // namespace fc
