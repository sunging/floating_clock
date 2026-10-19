#include "app.h"
#include "core/i18n.h"
#include "core/single_instance.h"
#include "version.h"

#include <QApplication>
#include <QCommandLineParser>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QImage>
#include <QJsonDocument>
#include <QLibraryInfo>
#include <QMessageBox>
#include <QSaveFile>

namespace {
class SilentDiagnosticSound final : public fc::SoundService {
public:
    void play(const fc::Config &) override {}
    void stop() override {}
};

void configureParser(QCommandLineParser &parser) {
    parser.setApplicationDescription(
        fc::I18n::tr("Floating clock, alarms, countdown and stopwatch"));
    parser.addHelpOption();
    parser.addVersionOption();
    parser.addOption({"config", fc::I18n::tr("Use the specified settings file"), "file"});
    parser.addOption(
        {"smoke-test", fc::I18n::tr("Run an isolated startup check; requires --config")});
    parser.addOption({"control", fc::I18n::tr("Open the control panel at startup")});
}
} // namespace

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    QCoreApplication::setApplicationName("FloatingClock");
    QCoreApplication::setApplicationVersion(FC_VERSION);
    QCoreApplication::setOrganizationName("FloatingClock");
    QApplication::setWindowIcon(QIcon(":/icons/clock.png"));
    auto &language = fc::LanguageManager::instance();
    language.apply("system");
    app.setQuitOnLastWindowClosed(false);
    QCommandLineParser bootstrap;
    configureParser(bootstrap);
    if (!bootstrap.parse(app.arguments()))
        bootstrap.process(app);
    const bool smoke = bootstrap.isSet("smoke-test");
    if (smoke && !bootstrap.isSet("config")) {
        qCritical("--smoke-test requires an isolated --config path");
        return 2;
    }
    const auto path =
        bootstrap.isSet("config") ? bootstrap.value("config") : fc::ConfigStore::defaultPath();
    fc::ConfigStore store(path);
    QString languageError;
    if (!language.apply(store.load().language, &languageError))
        qWarning().noquote() << languageError;
    QCommandLineParser parser;
    configureParser(parser);
    parser.process(app);
    fc::SingleInstance instance(path);
    QString error;
    const auto result = instance.start(&error);
    if (result == fc::SingleInstance::Result::ActivatedExisting)
        return smoke ? 3 : 0;
    if (result == fc::SingleInstance::Result::Error) {
        if (!smoke)
            QMessageBox::critical(nullptr, fc::I18n::tr("Floating Clock"), error);
        qCritical().noquote() << error;
        return 1;
    }
    fc::SystemTimeSource time;
    auto platform = fc::makePlatformServices();
    std::unique_ptr<fc::SoundService> sound;
    if (smoke)
        sound = std::make_unique<SilentDiagnosticSound>();
    else
        sound = std::make_unique<fc::SoundService>();
    fc::ApplicationController controller(store, time, *platform, *sound, !smoke);
    QObject::connect(&instance, &fc::SingleInstance::activated, &controller,
                     &fc::ApplicationController::showControl);
    if (parser.isSet("control"))
        controller.showControl();
    if (smoke) {
        QTimer::singleShot(250, &app, [&] {
            QString failure;
            bool ok = !QIcon(":/icons/clock.png").isNull() &&
                      QFileInfo(":/sounds/chime.wav").size() > 44 &&
                      fc::LanguageManager::applicationCatalogAvailable() &&
                      controller.clock().isVisible() && store.save(controller.config(), &failure) &&
                      store.saveRuntime(controller.timers().snapshot(), &failure);
#ifdef Q_OS_WIN
            const bool embeddedTranslation = fc::LanguageManager::embeddedQtCatalogAvailable();
            QFile notices(":/licenses/notices.txt");
            const bool embeddedLicenses =
                notices.open(QIODevice::ReadOnly) &&
                notices.readAll().contains("GNU AFFERO GENERAL PUBLIC LICENSE");
            ok = ok && embeddedTranslation && embeddedLicenses;
#endif
#ifdef FC_STATIC_QT
            ok =
                ok &&
                !QImage(":/qt-project.org/styles/commonstyle/images/warning-32.png").isNull() &&
                !QImage(":/qt-project.org/windows/cursors/images/closedhandcursor_32.png").isNull();
#endif
            if (ok) {
                QSaveFile report(QFileInfo(store.path()).absolutePath() + "/smoke-result.json");
                QJsonObject result{
                    {"version", FC_VERSION},
                    {"qt_version", qVersion()},
                    {"qt_linkage", QLibraryInfo::isSharedBuild() ? "shared" : "static"},
                    {"language", language.language()},
                    {"application_translation_catalog",
                     fc::LanguageManager::applicationCatalogAvailable()},
                    {"chinese_qt_translation", language.qtTranslationLoaded()},
                    {"platform", QGuiApplication::platformName()}};
#ifdef Q_OS_WIN
                result.insert("embedded_translation", embeddedTranslation);
                result.insert("embedded_licenses", embeddedLicenses);
#endif
                const auto bytes = QJsonDocument(result).toJson();
                ok = report.open(QIODevice::WriteOnly) && report.write(bytes) == bytes.size() &&
                     report.commit();
            }
            if (!ok)
                qCritical().noquote() << "Smoke test failed:" << failure;
            app.exit(ok ? 0 : 1);
        });
    }
    return app.exec();
}
