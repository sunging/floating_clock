#pragma once

#include <QCoreApplication>
#include <QLocale>
#include <QObject>
#include <QTranslator>
#include <memory>

namespace fc {

class I18n {
    Q_DECLARE_TR_FUNCTIONS(FloatingClock)
};

class LanguageManager final : public QObject {
    Q_OBJECT
public:
    static LanguageManager &instance();
    static QString resolve(const QString &setting, const QLocale &system = QLocale::system());
    static QString resolve(const QString &setting, const QStringList &preferred);
    bool apply(const QString &setting, QString *error = nullptr);
    QString language() const;
    bool qtTranslationLoaded() const;
    static bool applicationCatalogAvailable();
    static bool embeddedQtCatalogAvailable();

signals:
    void changed();

private:
    explicit LanguageManager(QObject *parent);
    QString language_;
    std::unique_ptr<QTranslator> applicationTranslation_;
    std::unique_ptr<QTranslator> qtTranslation_;
};

} // namespace fc
