#include "core/single_instance.h"

#include <QCryptographicHash>
#include <QDir>
#include <QFileInfo>
#include <QLocalSocket>

namespace fc {

SingleInstance::SingleInstance(const QString &configPath, QObject *parent) : QObject(parent) {
    directory_ = QFileInfo(configPath).absolutePath();
    const QString canonical = QFileInfo(directory_).canonicalFilePath();
    if (!canonical.isEmpty())
        directory_ = canonical;
    QString identity = QDir::cleanPath(directory_);
#ifdef Q_OS_WIN
    identity = identity.toLower();
#endif
    name_ =
        "floating-clock-" +
        QString::fromLatin1(QCryptographicHash::hash(identity.toUtf8(), QCryptographicHash::Sha256)
                                .toHex()
                                .left(32));
    server_.setSocketOptions(QLocalServer::UserAccessOption);
    connect(&server_, &QLocalServer::newConnection, this, [this] {
        while (auto *socket = server_.nextPendingConnection()) {
            socket->disconnectFromServer();
            socket->deleteLater();
            emit activated();
        }
    });
}

SingleInstance::Result SingleInstance::start(QString *error) {
    if (!QDir().mkpath(directory_)) {
        if (error)
            *error = QStringLiteral("无法创建配置目录：%1").arg(directory_);
        return Result::Error;
    }
    lock_ = std::make_unique<QLockFile>(directory_ + "/instance.lock");
    lock_->setStaleLockTime(0);
    if (!lock_->tryLock()) {
        QLocalSocket socket;
        socket.connectToServer(name_);
        if (socket.waitForConnected(1500))
            return Result::ActivatedExisting;
        if (error)
            *error = QStringLiteral("已有实例正在启动或无响应，请稍后重试。未修改其配置。");
        return Result::Error;
    }
    // Only the lock owner may remove an abandoned endpoint.
    QLocalServer::removeServer(name_);
    if (!server_.listen(name_)) {
        if (error)
            *error = QStringLiteral("无法建立单实例通信：%1").arg(server_.errorString());
        return Result::Error;
    }
    return Result::Primary;
}

QString SingleInstance::name() const {
    return name_;
}

} // namespace fc
