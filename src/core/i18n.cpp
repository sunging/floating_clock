#include "core/i18n.h"

#include <QApplication>
#include <QLibraryInfo>
#include <QPointer>
#include <QWidget>

namespace fc {
namespace {
bool loadQtCatalog(QTranslator &translation) {
    if (translation.load(":/translations/qtbase_zh_CN.qm"))
        return true;
    const auto directory = QCoreApplication::applicationDirPath();
    const QStringList paths{directory + "/translations", directory + "/../Resources/translations",
                            directory + "/../share/floating-clock/translations",
                            QLibraryInfo::path(QLibraryInfo::TranslationsPath)};
    for (const auto &path : paths)
        if (translation.load("qtbase_zh_CN", path))
            return true;
    return false;
}
} // namespace

LanguageManager::LanguageManager(QObject *parent) : QObject(parent) {}

LanguageManager &LanguageManager::instance() {
    static QPointer<LanguageManager> manager;
    if (!manager)
        manager = new LanguageManager(QCoreApplication::instance());
    return *manager;
}

QString LanguageManager::resolve(const QString &setting, const QLocale &system) {
    return resolve(setting, system.uiLanguages());
}

QString LanguageManager::resolve(const QString &setting, const QStringList &preferred) {
    if (setting == "en" || setting == "zh_CN")
        return setting;
    for (const auto &name : preferred) {
        const auto language = QLocale(name).language();
        if (language == QLocale::Chinese)
            return "zh_CN";
        if (language == QLocale::English)
            return "en";
    }
    return "en";
}

bool LanguageManager::apply(const QString &setting, QString *error) {
    const auto resolved = resolve(setting);
    if (resolved == language_)
        return true;
    std::unique_ptr<QTranslator> application;
    std::unique_ptr<QTranslator> qt;
    if (resolved == "zh_CN") {
        application = std::make_unique<QTranslator>();
        qt = std::make_unique<QTranslator>();
        if (!application->load(":/translations/floating-clock_zh_CN.qm") || !loadQtCatalog(*qt)) {
            if (error)
                *error = I18n::tr("Could not load the Chinese translation resources.");
            return false;
        }
    }
    if (applicationTranslation_)
        QCoreApplication::removeTranslator(applicationTranslation_.get());
    if (qtTranslation_)
        QCoreApplication::removeTranslator(qtTranslation_.get());
    applicationTranslation_ = std::move(application);
    qtTranslation_ = std::move(qt);
    if (qtTranslation_)
        QCoreApplication::installTranslator(qtTranslation_.get());
    if (applicationTranslation_)
        QCoreApplication::installTranslator(applicationTranslation_.get());
    language_ = resolved;
    const QLocale locale(resolved);
    QLocale::setDefault(locale);
    QApplication::setApplicationDisplayName(I18n::tr("Floating Clock"));
    for (auto *window : QApplication::topLevelWidgets())
        window->setLocale(locale);
    emit changed();
    return true;
}

QString LanguageManager::language() const {
    return language_;
}

bool LanguageManager::qtTranslationLoaded() const {
    return qtTranslation_ && !qtTranslation_->isEmpty();
}

bool LanguageManager::applicationCatalogAvailable() {
    QTranslator translation;
    return translation.load(":/translations/floating-clock_zh_CN.qm") &&
           !translation.translate("FloatingClock", "Stop reminders").isEmpty();
}

bool LanguageManager::embeddedQtCatalogAvailable() {
    QTranslator translation;
    return translation.load(":/translations/qtbase_zh_CN.qm") && !translation.isEmpty();
}

} // namespace fc
