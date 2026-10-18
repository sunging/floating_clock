#include "app.h"
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
#include <QTranslator>

namespace {
class SilentDiagnosticSound final : public fc::SoundService {
public:
    void play(const fc::Config &) override {}
    void stop() override {}
};
} // namespace

int main(int argc, char **argv) {
    QApplication app(argc, argv);
    QCoreApplication::setApplicationName("FloatingClock");
    QCoreApplication::setApplicationVersion(FC_VERSION);
    QCoreApplication::setOrganizationName("FloatingClock");
    QApplication::setWindowIcon(QIcon(":/icons/clock.png"));
    QTranslator qtTranslation;
#ifdef Q_OS_WIN
    const bool embeddedTranslation = qtTranslation.load(":/translations/qtbase_zh_CN.qm");
    if (embeddedTranslation)
        app.installTranslator(&qtTranslation);
#else
    const QString executableDir = QCoreApplication::applicationDirPath();
    const QStringList translationPaths{executableDir + "/translations",
                                       executableDir + "/../Resources/translations",
                                       executableDir + "/../share/floating-clock/translations",
                                       QLibraryInfo::path(QLibraryInfo::TranslationsPath)};
    for (const auto &directory : translationPaths) {
        if (qtTranslation.load("qtbase_zh_CN", directory)) {
            app.installTranslator(&qtTranslation);
            break;
        }
    }
#endif
    app.setQuitOnLastWindowClosed(false);
    QCommandLineParser parser;
    parser.setApplicationDescription(QStringLiteral("浮动时钟、闹钟、倒计时与秒表"));
    parser.addHelpOption();
    parser.addVersionOption();
    parser.addOption({"config", QStringLiteral("使用指定配置文件"), "file"});
    parser.addOption({"smoke-test", QStringLiteral("隔离启动检查；必须同时指定 --config")});
    parser.addOption({"control", QStringLiteral("启动后打开控制面板")});
    parser.process(app);
    const bool smoke = parser.isSet("smoke-test");
    if (smoke && !parser.isSet("config")) {
        qCritical("--smoke-test requires an isolated --config path");
        return 2;
    }
    const auto path =
        parser.isSet("config") ? parser.value("config") : fc::ConfigStore::defaultPath();
    fc::ConfigStore store(path);
    fc::SingleInstance instance(path);
    QString error;
    const auto result = instance.start(&error);
    if (result == fc::SingleInstance::Result::ActivatedExisting)
        return smoke ? 3 : 0;
    if (result == fc::SingleInstance::Result::Error) {
        if (!smoke)
            QMessageBox::critical(nullptr, QStringLiteral("浮动时钟"), error);
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
                      controller.clock().isVisible() && store.save(controller.config(), &failure) &&
                      store.saveRuntime(controller.timers().snapshot(), &failure);
#ifdef Q_OS_WIN
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
                    {"chinese_qt_translation", !qtTranslation.isEmpty()},
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
