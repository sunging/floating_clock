#include "core/single_instance.h"
#include "core/i18n.h"

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
            *error = I18n::tr("Could not create the settings directory: %1").arg(directory_);
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
            *error = I18n::tr("Another instance is starting or not responding. Try again later. "
                              "Its settings were not modified.");
        return Result::Error;
    }
    // Only the lock owner may remove an abandoned endpoint.
    QLocalServer::removeServer(name_);
    if (!server_.listen(name_)) {
        if (error)
            *error = I18n::tr("Could not establish single-instance communication: %1")
                         .arg(server_.errorString());
        return Result::Error;
    }
    return Result::Primary;
}

QString SingleInstance::name() const {
    return name_;
}

} // namespace fc
