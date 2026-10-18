#include "app.h"
#include "core/single_instance.h"
#include <QApplication>
#include <QDir>
#include <QFile>
#include <QImage>
#include <QJsonArray>
#include <QJsonDocument>
#include <QLibraryInfo>
#include <QMouseEvent>
#include <QPluginLoader>
#include <QScrollBar>
#include <QSettings>
#include <QSignalSpy>
#include <QTemporaryDir>
#include <QTest>
#include <QTranslator>
#include <limits>

namespace {
class FakeTime : public fc::TimeSource {
public:
    QDateTime wall = QDateTime(QDate(2026, 10, 19), QTime(7, 59));
    qint64 elapsed = 1000;
    QDateTime wallNow() const override {
        return wall;
    }
    qint64 elapsedNow() const override {
        return elapsed;
    }
    void advance(qint64 ms) {
        elapsed += ms;
        wall = wall.addMSecs(ms);
    }
};

class FakePlatform : public fc::PlatformServices {
public:
    FakePlatform() {
        capabilities_ = fc::Capabilities();
        capabilities_.displayPower = true;
    }
    bool through = false;
    int startupWrites = 0;
    fc::DisplayState state = fc::DisplayState::On;
    void start(QWidget *) override {}
    fc::DisplayState displayState() const override {
        return state;
    }
    void setClickThrough(QWidget *, bool value) override {
        through = value;
    }
    bool setAutostart(bool, const QString &, QString *) override {
        ++startupWrites;
        return true;
    }
    bool autostartEnabled() const override {
        return false;
    }
    void wake() {
        emit waking();
    }
};

class FakeSound : public fc::SoundService {
public:
    int plays = 0;
    int stops = 0;
    bool unavailable = false;
    bool audible = false;
    QString path;
    void play(const fc::Config &config) override {
        ++plays;
        path = config.soundPath;
        audible = config.soundMode != "silent" && !unavailable;
        if (unavailable)
            emit failed(QStringLiteral("测试音频设备不可用"));
    }
    void stop() override {
        ++stops;
        audible = false;
    }
};

#ifdef Q_OS_WIN
struct WaveState {
    QStringList calls;
    QByteArray wave;
    QString file;
    bool aliasOk = true;
    bool fileOk = true;
    bool memoryOk = true;
};

class FakeWavePlayer : public fc::WavePlayer {
public:
    explicit FakeWavePlayer(WaveState &state) : state_(state) {}
    bool playAlias(const QString &alias) override {
        state_.calls.append("alias:" + alias);
        return state_.aliasOk;
    }
    bool playFile(const QString &path) override {
        state_.calls.append("file");
        state_.file = path;
        return state_.fileOk;
    }
    bool playMemory(const QByteArray &wave) override {
        state_.calls.append("memory");
        state_.wave = wave;
        return state_.memoryOk;
    }
    void stop() override {
        state_.calls.append("stop");
    }

private:
    WaveState &state_;
};
#endif

class ClockTests : public QObject {
    Q_OBJECT
private slots:
    void qtLinkageAndStaticPlugins() {
#ifdef FC_STATIC_QT
        QVERIFY(!QLibraryInfo::isSharedBuild());
        QStringList classes;
        for (const auto &plugin : QPluginLoader::staticPlugins())
            classes.append(plugin.metaData().value("className").toString());
        QVERIFY(classes.contains("QWindowsIntegrationPlugin"));
        QVERIFY(classes.contains("QOffscreenIntegrationPlugin"));
        QVERIFY(classes.contains("QModernWindowsStylePlugin"));
        QVERIFY(!QImage(":/qt-project.org/styles/commonstyle/images/warning-32.png").isNull());
        QVERIFY(
            !QImage(":/qt-project.org/windows/cursors/images/closedhandcursor_32.png").isNull());
#else
        QVERIFY(QLibraryInfo::isSharedBuild());
#endif
    }
#ifdef Q_OS_WIN
    void embeddedWindowsTranslationAndLicenses() {
        QTranslator translation;
        QVERIFY(translation.load(":/translations/qtbase_zh_CN.qm"));
        const auto cancel = translation.translate("QPlatformTheme", "Cancel");
        QVERIFY(!cancel.isEmpty());
        QVERIFY(cancel.contains(QStringLiteral("取消")));
        QFile notices(":/licenses/notices.txt");
        QVERIFY(notices.open(QIODevice::ReadOnly));
        const auto contents = notices.readAll();
        QVERIFY(contents.contains("GNU AFFERO GENERAL PUBLIC LICENSE"));
        QVERIFY(contents.contains("GNU GENERAL PUBLIC LICENSE"));
#ifdef FC_STATIC_QT
        QVERIFY(contents.contains("static-qt-build.json"));
        QVERIFY(contents.contains("GCC RUNTIME LIBRARY EXCEPTION"));
#endif
        fc::AboutDialog dialog;
        const auto *text = dialog.findChild<QPlainTextEdit *>("licenseText");
        QVERIFY(text);
        QVERIFY(text->isReadOnly());
        QCOMPARE(text->toPlainText(), QString::fromUtf8(contents));
    }

    void nativeWaveSystemAndStop() {
        WaveState state;
        fc::SoundService sound(std::make_unique<FakeWavePlayer>(state));
        QSignalSpy errors(&sound, &fc::SoundService::failed);
        fc::Config config;
        sound.play(config);
        QCOMPARE(state.calls, QStringList({"stop", "alias:SystemHand"}));
        sound.stop();
        QCOMPARE(state.calls.last(), QString("stop"));
        QVERIFY(errors.isEmpty());
    }
    void nativeWaveCustomAndFallback() {
        QTemporaryDir directory;
        const QString path = directory.filePath(QStringLiteral("中文提示音.wav"));
        QVERIFY(QFile::copy(":/sounds/chime.wav", path));
        WaveState state;
        fc::SoundService sound(std::make_unique<FakeWavePlayer>(state));
        QSignalSpy errors(&sound, &fc::SoundService::failed);
        fc::Config config;
        config.soundMode = "custom";
        config.soundPath = path;
        sound.play(config);
        QCOMPARE(state.file, path);
        QCOMPARE(state.calls, QStringList({"stop", "file"}));
        QVERIFY(errors.isEmpty());
        state.fileOk = false;
        sound.play(config);
        QCOMPARE(errors.size(), 1);
        QCOMPARE(state.calls.last(), QString("memory"));
        QVERIFY(state.wave.startsWith("RIFF"));
        QVERIFY(state.wave.size() > 44);
        state.calls.clear();
        config.soundPath = directory.filePath("missing.wav");
        sound.play(config);
        QCOMPARE(errors.size(), 2);
        QCOMPARE(state.calls, QStringList({"stop", "memory"}));
    }
    void nativeWaveSilentAndUnavailableDevice() {
        WaveState state;
        fc::SoundService sound(std::make_unique<FakeWavePlayer>(state));
        QSignalSpy errors(&sound, &fc::SoundService::failed);
        fc::Config config;
        config.soundMode = "silent";
        sound.play(config);
        QCOMPARE(state.calls, QStringList({"stop"}));
        config.soundMode = "system";
        state.aliasOk = false;
        state.memoryOk = false;
        sound.play(config);
        QCOMPARE(state.calls.last(), QString("memory"));
        QCOMPARE(errors.size(), 1);
    }
    void nativeWaveTimeoutCleanup() {
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        WaveState state;
        fc::SoundService sound(std::make_unique<FakeWavePlayer>(state));
        fc::ApplicationController controller(store, time, platform, sound, false);
        fc::Alarm alarm;
        alarm.time = "07:59";
        alarm.timeoutSeconds = 1;
        controller.config().alarms.append(alarm);
        controller.tick();
        QVERIFY(controller.reminders().active());
        QCOMPARE(state.calls.last(), QString("alias:SystemHand"));
        time.advance(1000);
        controller.tick();
        QVERIFY(!controller.reminders().active());
        QCOMPARE(state.calls.last(), QString("stop"));
    }
#endif
    void boolParsing_data() {
        QTest::addColumn<QVariant>("raw");
        QTest::addColumn<bool>("expected");
        for (const auto &input : QStringList{"1", "true", "TRUE", "yes", "on"})
            QTest::newRow(qUtf8Printable(input)) << QVariant(input) << true;
        for (const auto &input : QStringList{"0", "false", "FALSE", "off", "no", "", "bad"})
            QTest::newRow(qUtf8Printable("false-" + input)) << QVariant(input) << false;
    }
    void boolParsing() {
        QFETCH(QVariant, raw);
        QFETCH(bool, expected);
        QCOMPARE(fc::readBool(raw), expected);
    }
    void numericNormalization() {
        QCOMPARE(fc::readInt("bad", 48, 8, 400), 48);
        QCOMPARE(fc::readInt("1e100", 48, 8, 400), 400);
        QCOMPARE(fc::readInt(-100, 48, 8, 400), 8);
        QCOMPARE(fc::readInt(48.9, 48, 8, 400), 48);
        QCOMPARE(fc::readReal(std::numeric_limits<double>::infinity(), .75, .1, 1), .75);
        QCOMPARE(fc::readReal(std::numeric_limits<double>::quiet_NaN(), .75, .1, 1), .75);
        QCOMPARE(fc::readReal("bad", .75, .1, 1), .75);
    }
    void invalidAlarm_data() {
        QTest::addColumn<QString>("value");
        for (const auto &text :
             QStringList{"8:00", "24:00", "00:60", "-1:00", "12:3", "aa:bb", "１２:００", ""})
            QTest::newRow(qUtf8Printable(text)) << text;
    }
    void invalidAlarm() {
        QFETCH(QString, value);
        QVERIFY(!fc::Alarm::fromJson(QJsonObject{{"time", value}}));
    }
    void alarmCompatibility() {
        QVERIFY(!fc::Alarm::fromJson(QJsonValue()));
        QVERIFY(!fc::Alarm::fromJson(QJsonArray()));
        auto alarm =
            fc::Alarm::fromJson(QJsonObject{{"repeat_daily", "false"},
                                            {"enabled", "false"},
                                            {"repeat_weekdays", QJsonArray{4, 2, 2, -1, 9, "3"}}});
        QVERIFY(alarm.has_value());
        QVERIFY(alarm->once());
        QVERIFY(!alarm->enabled);
        QCOMPARE(alarm->weekdays, QVector<int>({2, 3, 4}));
        QVERIFY(!alarm->id.isEmpty());
        QVERIFY(!alarm->timeoutSeconds.has_value());
        alarm->timeoutSeconds = 90;
        QCOMPARE(fc::Alarm::fromJson(alarm->toJson())->toJson(), alarm->toJson());
    }
    void repeatRules_data() {
        QTest::addColumn<QString>("repeat");
        QTest::addColumn<int>("day");
        QTest::addColumn<bool>("expected");
        for (const QString &repeat : QStringList{"once", "daily", "weekdays", "custom"})
            for (int day = 0; day < 7; ++day) {
                const bool hit = repeat == "once" || repeat == "daily" ||
                                 (repeat == "weekdays" && day < 5) ||
                                 (repeat == "custom" && (day == 2 || day == 6));
                QTest::newRow(qUtf8Printable(repeat + QString::number(day)))
                    << repeat << day << hit;
            }
    }
    void repeatRules() {
        QFETCH(QString, repeat);
        QFETCH(int, day);
        QFETCH(bool, expected);
        fc::Alarm alarm;
        alarm.repeat = repeat;
        alarm.weekdays = {2, 6};
        const QDateTime now(QDate(2026, 10, 19).addDays(day), QTime(8, 0));
        QCOMPARE(alarm.matches(now), expected);
        QVERIFY(!alarm.matches(now.addSecs(60)));
        alarm.enabled = false;
        QVERIFY(!alarm.matches(now));
    }
    void alarmScheduling() {
        fc::Config config;
        fc::Alarm once;
        once.repeat = "once";
        fc::Alarm daily;
        config.alarms = {once, daily};
        fc::AlarmScheduler scheduler;
        const QDateTime now(QDate(2026, 10, 19), QTime(8, 0));
        QVERIFY(scheduler.check(config, now, false).isEmpty());
        QVERIFY(config.alarms[0].enabled);
        QCOMPARE(scheduler.check(config, now, true).size(), 2);
        QVERIFY(!config.alarms[0].enabled);
        QVERIFY(scheduler.check(config, now.addSecs(5), true).isEmpty());
        config.alarms.append(fc::Alarm());
        QCOMPARE(scheduler.check(config, now.addSecs(10), true).size(), 1);
        QVERIFY(scheduler.check(config, now.addSecs(60), true).isEmpty());
        QVERIFY(scheduler.check(config, now, true).isEmpty());
        QCOMPARE(scheduler.check(config, now.addDays(1), true).size(), 2);
    }
    void independentReminderDeadlines() {
        fc::ReminderController reminders;
        fc::Config config;
        fc::Alarm a;
        a.timeoutSeconds = 1;
        a.label = "one";
        reminders.add(a, config, 1000);
        a.timeoutSeconds = 3;
        a.label = "two";
        reminders.add(a, config, 1000);
        QVERIFY(!reminders.expire(1999));
        QVERIFY(reminders.expire(2000));
        QCOMPARE(reminders.items().size(), 1);
        QCOMPARE(reminders.title(), QString("two"));
        config.alarmTimeoutSeconds = 2;
        reminders.addCountdown(config, 2500);
        QVERIFY(reminders.expire(4000));
        QCOMPARE(reminders.items().size(), 1);
        QCOMPARE(reminders.items().first().expiresAt, qint64(4500));
        QVERIFY(reminders.expire(4500));
        QVERIFY(!reminders.active());
        QVERIFY(!reminders.expire(9999));
    }
    void timeoutDefaults_data() {
        QTest::addColumn<int>("global");
        QTest::addColumn<int>("override");
        QTest::addColumn<int>("expected");
        QTest::newRow("default") << 60 << -1 << 60;
        QTest::newRow("global") << 30 << -1 << 30;
        QTest::newRow("override") << 30 << 120 << 120;
        QTest::newRow("zero") << 0 << -1 << 1;
        QTest::newRow("large") << 3601 << -1 << 3600;
    }
    void timeoutDefaults() {
        QFETCH(int, global);
        QFETCH(int, override);
        QFETCH(int, expected);
        fc::Alarm alarm;
        if (override >= 0)
            alarm.timeoutSeconds = override;
        fc::ReminderController reminders;
        fc::Config config;
        config.alarmTimeoutSeconds = global;
        reminders.add(alarm, config, 0);
        QCOMPARE(reminders.items().first().expiresAt, qint64(expected) * 1000);
    }
    void configRoundtrip() {
        QTemporaryDir directory;
        QVERIFY(directory.isValid());
        fc::ConfigStore store(directory.filePath("config.ini"));
        fc::Config config;
        config.fontSize = 91;
        config.opacity = .33;
        config.color = "#112233";
        config.autoColor = true;
        config.darkBackgroundColor = "#dddddd";
        config.lightBackgroundColor = "#111111";
        config.showSeconds = false;
        config.showDate = true;
        config.clickThrough = false;
        config.startOnBoot = true;
        config.soundMode = "custom";
        config.soundAlias = "SystemDefault";
        config.soundPath = QStringLiteral("C:/中文/提示音.wav");
        config.ringWhenScreenOff = true;
        config.posX = -300;
        config.posY = 123;
        config.popupTextColor = "#abcdef";
        config.popupBackgroundColor = "#102030";
        config.popupOpacity = .21;
        config.popupFlash = false;
        config.popupFontScale = 2.2;
        config.popupLayout = "time_label";
        config.alarmTimeoutSeconds = 91;
        fc::Alarm alarm;
        alarm.timeoutSeconds = 121;
        alarm.content = QStringLiteral("多行\n内容");
        config.alarms = {alarm};
        QString error;
        QVERIFY2(store.save(config, &error), qUtf8Printable(error));
        const auto loaded = store.load(&error);
        QVERIFY(error.isEmpty());
        QCOMPARE(loaded.fontSize, config.fontSize);
        QCOMPARE(loaded.opacity, config.opacity);
        QCOMPARE(loaded.color, config.color);
        QCOMPARE(loaded.autoColor, config.autoColor);
        QCOMPARE(loaded.darkBackgroundColor, config.darkBackgroundColor);
        QCOMPARE(loaded.lightBackgroundColor, config.lightBackgroundColor);
        QCOMPARE(loaded.showSeconds, config.showSeconds);
        QCOMPARE(loaded.showDate, config.showDate);
        QCOMPARE(loaded.clickThrough, config.clickThrough);
        QCOMPARE(loaded.startOnBoot, config.startOnBoot);
        QCOMPARE(loaded.soundMode, config.soundMode);
        QCOMPARE(loaded.soundAlias, config.soundAlias);
        QCOMPARE(loaded.soundPath, config.soundPath);
        QCOMPARE(loaded.ringWhenScreenOff, config.ringWhenScreenOff);
        QCOMPARE(loaded.posX, config.posX);
        QCOMPARE(loaded.posY, config.posY);
        QCOMPARE(loaded.popupTextColor, config.popupTextColor);
        QCOMPARE(loaded.popupBackgroundColor, config.popupBackgroundColor);
        QCOMPARE(loaded.popupOpacity, config.popupOpacity);
        QCOMPARE(loaded.popupFlash, config.popupFlash);
        QCOMPARE(loaded.popupFontScale, config.popupFontScale);
        QCOMPARE(loaded.popupLayout, config.popupLayout);
        QCOMPARE(loaded.alarmTimeoutSeconds, config.alarmTimeoutSeconds);
        QCOMPARE(loaded.alarms[0].toJson(), alarm.toJson());
        QSettings settings(store.path(), QSettings::IniFormat);
        for (const auto &key : fc::ConfigStore::scalarKeys())
            QVERIFY2(settings.contains(key), qUtf8Printable(key));
        QCOMPARE(fc::ConfigStore::scalarKeys().size(), 23);
        QVERIFY(store.save(fc::Config()));
        QVERIFY(!store.load().posX);
    }
    void configMigration() {
        QTemporaryDir directory;
        const auto path = directory.filePath("config.ini");
        {
            QSettings old(path, QSettings::IniFormat);
            old.setValue("font_size", "nan");
            old.setValue("opacity", "inf");
            old.setValue("pos_x", "1e100");
            old.setValue("color", "bad color");
            old.setValue("alarm_timeout_seconds", "bad");
            old.setValue(
                "alarms",
                R"([null,{"id":"same","time":"08:00","repeat_daily":false},{"id":"same","time":"09:00"},{"time":"bad"}])");
        }
        fc::ConfigStore store(path);
        QString warning;
        auto cfg = store.load(&warning);
        QVERIFY(!warning.isEmpty());
        QCOMPARE(cfg.fontSize, 48);
        QCOMPARE(cfg.opacity, .75);
        QCOMPARE(cfg.color, QString("#FFFFFF"));
        QCOMPARE(cfg.alarmTimeoutSeconds, 60);
        QVERIFY(!cfg.posX);
        QCOMPARE(cfg.alarms.size(), 2);
        QVERIFY(cfg.alarms[0].once());
        QVERIFY(cfg.alarms[0].id != cfg.alarms[1].id);
        QVERIFY(store.save(cfg));
        QCOMPARE(QDir(directory.path()).entryList({"*.bak"}, QDir::Files).size(), 1);
        {
            QSettings malformed(path, QSettings::IniFormat);
            malformed.setValue("alarms", "broken JSON");
        }
        cfg = store.load(&warning);
        QVERIFY(!warning.isEmpty());
        QVERIFY(store.save(cfg));
        QCOMPARE(QDir(directory.path()).entryList({"*.bak"}, QDir::Files).size(), 2);
        QVERIFY(store.save(cfg));
        QCOMPARE(QDir(directory.path()).entryList({"*.bak"}, QDir::Files).size(), 2);
    }
    void invalidConfig_data() {
        QTest::addColumn<QString>("value");
        for (const auto &input : QStringList{"null", "{}", "not json", "42"})
            QTest::newRow(qUtf8Printable(input)) << input;
    }
    void invalidConfig() {
        QFETCH(QString, value);
        QTemporaryDir directory;
        const auto path = directory.filePath("config.ini");
        {
            QSettings settings(path, QSettings::IniFormat);
            settings.setValue("alarms", value);
        }
        QString warning;
        QVERIFY(fc::ConfigStore(path).load(&warning).alarms.isEmpty());
        QVERIFY(!warning.isEmpty());
    }
    void failedSaveAndFutureSchema() {
        QTemporaryDir directory;
        QFile blocker(directory.filePath("blocker"));
        QVERIFY(blocker.open(QIODevice::WriteOnly));
        blocker.close();
        QString error;
        QVERIFY(!fc::ConfigStore(blocker.fileName() + "/config.ini").save(fc::Config(), &error));
        QVERIFY(!error.isEmpty());
        const auto path = directory.filePath("future.ini");
        {
            QSettings settings(path, QSettings::IniFormat);
            settings.setValue("schema_version", 999);
            settings.setValue("font_size", 123);
        }
        QVERIFY(!fc::ConfigStore(path).save(fc::Config(), &error));
        QCOMPARE(fc::ConfigStore(path).load().fontSize, 123);
    }
    void configImportAndRuntimeIsolation() {
        QTemporaryDir directory;
        fc::ConfigStore old(directory.filePath("old.ini"));
        fc::Config config;
        config.fontSize = 99;
        QVERIFY(old.save(config));
        fc::ConfigStore target(directory.filePath("new/config.ini"));
        QVERIFY(target.save(fc::Config()));
        FakeTime time;
        fc::Timers timers(time);
        timers.startCountdown(10000);
        const auto snapshot = timers.snapshot();
        QVERIFY(target.saveRuntime(snapshot));
        fc::Config imported;
        QVERIFY(target.importFile(old.path(), &imported));
        QCOMPARE(imported.fontSize, 99);
        QCOMPARE(target.loadRuntime(), snapshot);
        QCOMPARE(old.load().fontSize, 99);
        QVERIFY(!QDir(directory.filePath("new")).entryList({"*.bak"}).isEmpty());
    }
    void futureRuntimeIsPreserved() {
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        const QByteArray original = R"({"schema_version":999,"future_timer_state":"keep"})";
        QFile file(store.runtimePath());
        QVERIFY(file.open(QIODevice::WriteOnly));
        QCOMPARE(file.write(original), original.size());
        file.close();
        QString warning;
        QVERIFY(store.loadRuntime(&warning).isEmpty());
        QVERIFY(warning.contains(QStringLiteral("保存已禁用")));
        FakeTime time;
        QString error;
        QVERIFY(!store.saveRuntime(fc::Timers(time).snapshot(), &error));
        QVERIFY(!error.isEmpty());
        QVERIFY(file.open(QIODevice::ReadOnly));
        QCOMPARE(file.readAll(), original);
    }
    void countdownLifecycleAndClockChanges() {
        FakeTime time;
        fc::Timers timers(time);
        timers.startCountdown(10000);
        time.advance(1234);
        QCOMPARE(timers.countdownRemaining(), qint64(8766));
        time.wall = time.wall.addYears(1);
        QCOMPARE(timers.countdownRemaining(), qint64(8766));
        timers.pauseCountdown();
        time.advance(90000);
        QCOMPARE(timers.countdownRemaining(), qint64(8766));
        timers.resumeCountdown();
        time.advance(8766);
        QVERIFY(timers.advance());
        QVERIFY(!timers.advance());
        QCOMPARE(timers.countdownRemaining(), qint64(0));
        timers.resetCountdown();
        QCOMPARE(timers.countdownState(), fc::Timers::State::Idle);
        QCOMPARE(timers.countdownRemaining(), qint64(10000));
    }
    void countdownRestart_data() {
        QTest::addColumn<qint64>("delay");
        QTest::addColumn<qint64>("remaining");
        QTest::newRow("before deadline") << qint64(2000) << qint64(7000);
        QTest::newRow("at deadline") << qint64(9000) << qint64(0);
        QTest::newRow("days later") << qint64(86400000) << qint64(0);
    }
    void countdownRestart() {
        QFETCH(qint64, delay);
        QFETCH(qint64, remaining);
        FakeTime time;
        fc::Timers original(time);
        original.startCountdown(10000);
        time.advance(1000);
        const auto saved = original.snapshot();
        time.advance(delay);
        time.elapsed = 12;
        fc::Timers restored(time);
        restored.restore(saved);
        QCOMPARE(restored.countdownRemaining(), remaining);
        QVERIFY(!restored.advance());
    }
    void stopwatchRestartAndLaps() {
        FakeTime time;
        fc::Timers timers(time);
        timers.startStopwatch();
        time.advance(1250);
        timers.lap();
        time.advance(750);
        timers.lap();
        QCOMPARE(timers.laps(), QVector<qint64>({1250, 2000}));
        time.wall = time.wall.addSecs(-3600);
        QCOMPARE(timers.stopwatchElapsed(), qint64(2000));
        const auto saved = timers.snapshot();
        time.advance(100000);
        fc::Timers restored(time);
        restored.restore(saved);
        QVERIFY(!restored.stopwatchRunning());
        QCOMPARE(restored.stopwatchElapsed(), qint64(2000));
        QCOMPARE(restored.laps(), timers.laps());
        restored.startStopwatch();
        time.advance(125);
        restored.pauseStopwatch();
        time.advance(500);
        QCOMPARE(restored.stopwatchElapsed(), qint64(2125));
        restored.resetStopwatch();
        QCOMPARE(restored.stopwatchElapsed(), qint64(0));
        QVERIFY(restored.laps().isEmpty());
    }
    void corruptRuntime() {
        FakeTime time;
        fc::Timers timers(time);
        timers.restore({{"countdown_state", 99},
                        {"countdown_duration_ms", -100},
                        {"display_mode", "bad"},
                        {"stopwatch_elapsed_ms", -40},
                        {"laps_ms", QJsonArray{"bad", -1, 1e100}}});
        QCOMPARE(timers.displayMode, QString("clock"));
        QCOMPARE(timers.countdownState(), fc::Timers::State::Idle);
        QCOMPARE(timers.stopwatchElapsed(), qint64(0));
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        QFile file(store.runtimePath());
        QVERIFY(file.open(QIODevice::WriteOnly));
        file.write("not json");
        file.close();
        QString warning;
        QVERIFY(store.loadRuntime(&warning).isEmpty());
        QVERIFY(!warning.isEmpty());
    }
    void geometry() {
        const QRect primary(0, 0, 1920, 1080);
        const QRect left(-1280, 0, 1280, 1024);
        QCOMPARE(fc::screenAreaFor(QRect(-800, 40, 300, 100), {primary, left}, primary), left);
        QCOMPARE(fc::clampedPosition(QRect(-800, 40, 300, 100), left), QPoint(-800, 40));
        QCOMPARE(fc::clampedPosition(QRect(-4000, 9000, 300, 100), primary), QPoint(0, 980));
        QCOMPARE(fc::clampedPosition(QRect(0, 0, 4000, 2000), left), left.topLeft());
        QCOMPARE(fc::screenAreaFor(QRect(9000, 9000, 300, 100), {primary, left}, primary), primary);
    }
    void autoColorRefreshAndFailure() {
        QImage background(32, 16, QImage::Format_RGB32);
        background.fill(Qt::white);
        int samples = 0;
        fc::ClockWindow window(nullptr, [&](const QRect &) {
            ++samples;
            return background;
        });
        window.setDisplay("08:00:00", "08:00:00");
        window.show();
        fc::Config config;
        config.color = "#FF00FF";
        config.autoColor = true;
        window.applyConfig(config);
        const auto *label = window.findChild<QLabel *>();
        QVERIFY(label);
        QCOMPARE(samples, 1);
        QVERIFY(label->styleSheet().contains(config.lightBackgroundColor));
        background.fill(Qt::black);
        config.posX = 40;
        config.posY = 50;
        window.applyConfig(config);
        QCOMPARE(samples, 2);
        QVERIFY(label->styleSheet().contains(config.darkBackgroundColor));
        background = QImage();
        window.sampleBackground();
        QVERIFY(label->styleSheet().contains(config.darkBackgroundColor));
        config.autoColor = false;
        window.applyConfig(config);
        QCOMPARE(samples, 3);
        QVERIFY(label->styleSheet().contains(config.color));
    }
    void interactiveSurfaceRestoresTransparency() {
        fc::ClockWindow window;
        window.setDisplay("08:00:00", "08:00:00");
        window.setInteractive(false);
        QCOMPARE(window.grab().toImage().pixelColor(2, 2).alpha(), 0);
        window.setInteractive(true);
        QVERIFY(window.grab().toImage().pixelColor(2, 2).alpha() > 0);
        window.setInteractive(false);
        QCOMPARE(window.grab().toImage().pixelColor(2, 2).alpha(), 0);
    }
    void appDragPersistsPosition_data() {
        QTest::addColumn<bool>("moveMode");
        QTest::newRow("click-through disabled") << false;
        QTest::newRow("temporary move mode") << true;
    }
    void appDragPersistsPosition() {
        QFETCH(bool, moveMode);
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        fc::Config config;
        config.posX = 100;
        config.posY = 100;
        config.clickThrough = moveMode;
        QVERIFY(store.save(config));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        fc::ApplicationController controller(store, time, platform, sound, false);
        if (moveMode)
            controller.setMoveMode(true);
        auto &window = controller.clock();
        const auto start = window.pos();
        const QPointF local(2, 2);
        const QPointF global = window.mapToGlobal(local.toPoint());
        QMouseEvent press(QEvent::MouseButtonPress, local, global, Qt::LeftButton, Qt::LeftButton,
                          Qt::NoModifier);
        QApplication::sendEvent(&window, &press);
        QVERIFY(window.isDragging());
        const QPoint offset(80, 30);
        QMouseEvent move(QEvent::MouseMove, local + offset, global + offset, Qt::NoButton,
                         Qt::LeftButton, Qt::NoModifier);
        QApplication::sendEvent(&window, &move);
        time.advance(1000);
        controller.tick();
        window.restorePosition();
        QCOMPARE(window.pos(), start + offset);
        QMouseEvent release(QEvent::MouseButtonRelease, local, global + offset, Qt::LeftButton,
                            Qt::NoButton, Qt::NoModifier);
        QApplication::sendEvent(&window, &release);
        QVERIFY(!window.isDragging());
        QCOMPARE(window.pos(), start + offset);
        QCOMPARE(controller.config().posX.value(), window.x());
        QCOMPARE(controller.config().posY.value(), window.y());
        QCOMPARE(store.load().posX.value(), window.x());
        QCOMPARE(store.load().posY.value(), window.y());
        QCOMPARE(store.load().clickThrough, moveMode);
        QCOMPARE(platform.through, moveMode);
        QCOMPARE(platform.startupWrites, 0);
    }
    void popupBoundaries_data() {
        QTest::addColumn<int>("size");
        QTest::addColumn<QString>("layout");
        QTest::addColumn<bool>("flash");
        for (int size : {8, 48, 400})
            for (const auto &layout : QStringList{"label_time", "time_label", "label_only"})
                for (bool flash : {false, true})
                    QTest::newRow(
                        qUtf8Printable(QString::number(size) + layout + QString::number(flash)))
                        << size << layout << flash;
    }
    void popupBoundaries() {
        QFETCH(int, size);
        QFETCH(QString, layout);
        QFETCH(bool, flash);
        fc::ClockWindow window;
        fc::Config config;
        config.fontSize = size;
        config.popupLayout = layout;
        config.popupFlash = flash;
        config.popupFontScale = 3;
        window.applyConfig(config);
        window.setDisplay("08:00:00", "08:00:00");
        window.setReminder(
            QStringLiteral("很长的提醒"),
            QStringLiteral("中文内容和长单词 abcdefghijklmnopqrstuvwxyz\n").repeated(100));
        window.show();
        QApplication::processEvents();
        const auto area = window.screen()->availableGeometry();
        QVERIFY(window.width() <= area.width() * .8 + 1);
        QVERIFY(window.height() <= area.height() * .8 + 1);
        auto *stop = window.findChild<QPushButton *>("stopReminder");
        QVERIFY(stop->isVisible());
        QVERIFY(window.rect().contains(stop->mapTo(&window, stop->rect().center())));
        auto *text = window.findChild<QPlainTextEdit *>("reminderText");
        window.setDisplay("08:00:01", "08:00:01");
        QCOMPARE(text->toPlainText().contains("08:00:01"), layout != "label_only");
        QSignalSpy dismissed(&window, &fc::ClockWindow::dismissed);
        QTest::mouseClick(text->viewport(), Qt::LeftButton);
        QCOMPARE(dismissed.count(), 1);
        QTest::mouseClick(text->viewport(), Qt::RightButton);
        QCOMPARE(dismissed.count(), 1);
    }
    void settingsCopyAndConsumedIdentity() {
        fc::Config config;
        fc::Alarm first;
        first.repeat = "once";
        fc::Alarm second = first;
        second.id = "second";
        config.alarms = {first, second};
        fc::SettingsDialog dialog(config, fc::Capabilities());
        dialog.findChild<QSpinBox *>("fontSize")->setValue(90);
        QCOMPARE(config.fontSize, 48);
        QCOMPARE(dialog.resultConfig().fontSize, 90);
        dialog.markAlarmFired(first);
        QVERIFY(!dialog.resultConfig().alarms[0].enabled);
        QVERIFY(dialog.resultConfig().alarms[1].enabled);
        auto *list = dialog.findChild<QListWidget *>("alarmList");
        list->item(0)->setCheckState(Qt::Checked);
        QVERIFY(dialog.resultConfig().alarms[0].enabled);
    }
    void alarmEditorTimeout() {
        fc::Alarm alarm;
        fc::AlarmEditDialog editor(alarm);
        QVERIFY(!editor.resultAlarm().timeoutSeconds);
        editor.findChild<QCheckBox *>("inheritTimeout")->setChecked(false);
        editor.findChild<QSpinBox *>("alarmTimeout")->setValue(123);
        QCOMPARE(editor.resultAlarm().timeoutSeconds.value(), 123);
        QCOMPARE(editor.resultAlarm().id, alarm.id);
    }
    void nestedEditorPreservesConsumption() {
        fc::Alarm alarm;
        alarm.repeat = "once";
        fc::AlarmEditDialog editor(alarm);
        editor.findChild<QLineEdit *>("alarmLabel")->setText(QStringLiteral("改名"));
        editor.markAlarmFired(alarm);
        QVERIFY(!editor.resultAlarm().enabled);
        fc::AlarmEditDialog rescheduled(alarm);
        rescheduled.findChild<QTimeEdit *>("alarmTime")->setTime(QTime(9, 0));
        rescheduled.markAlarmFired(alarm);
        QVERIFY(rescheduled.resultAlarm().enabled);
    }
    void settingsCommitDuringAlarm() {
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        fc::ApplicationController controller(store, time, platform, sound, false);
        fc::Alarm alarm;
        alarm.repeat = "once";
        controller.config().alarms = {alarm};
        QTimer::singleShot(0, [&] {
            auto *dialog = qobject_cast<fc::SettingsDialog *>(qApp->activeModalWidget());
            Q_ASSERT(dialog);
            dialog->findChild<QSpinBox *>("fontSize")->setValue(90);
            time.wall = time.wall.addSecs(60);
            controller.tick();
            dialog->accept();
        });
        controller.openSettings();
        QCOMPARE(controller.config().fontSize, 90);
        QVERIFY(!controller.config().alarms[0].enabled);
        QVERIFY(!store.load().alarms[0].enabled);
        QVERIFY(controller.reminders().active());
        QVERIFY(!platform.through);
        QCOMPARE(platform.startupWrites, 0);
    }
    void settingsCancelRestoresAppearanceAndStopsPreview() {
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        fc::ApplicationController controller(store, time, platform, sound, false);
        QTimer::singleShot(0, [&] {
            auto *dialog = qobject_cast<fc::SettingsDialog *>(qApp->activeModalWidget());
            Q_ASSERT(dialog);
            dialog->findChild<QSpinBox *>("fontSize")->setValue(90);
            dialog->reminderPreviewRequested(dialog->resultConfig());
            dialog->soundPreviewRequested(dialog->resultConfig());
            QVERIFY(controller.clock().reminderVisible());
            QVERIFY(!platform.through);
            dialog->reject();
        });
        controller.openSettings();
        QCOMPARE(controller.config().fontSize, 48);
        QVERIFY(!controller.clock().reminderVisible());
        QVERIFY(platform.through);
        QCOMPARE(sound.plays, 1);
        QVERIFY(sound.stops > 0);
        QVERIFY(!QFileInfo::exists(store.path()));
    }
    void popupKeepsScrollAtBottom() {
        fc::ClockWindow window;
        window.setDisplay("08:00:00", "08:00:00");
        window.setReminder(QStringLiteral("长提醒"), QStringLiteral("内容\n").repeated(200));
        window.show();
        QApplication::processEvents();
        auto *text = window.findChild<QPlainTextEdit *>("reminderText");
        auto *scroll = text->verticalScrollBar();
        QVERIFY(scroll->maximum() > 0);
        scroll->setValue(scroll->maximum());
        window.setDisplay("08:00:01", "08:00:01");
        QApplication::processEvents();
        QCOMPARE(scroll->value(), scroll->maximum());
    }
    void visualSnapshots() {
        const auto directory = qEnvironmentVariable("FC_TEST_SCREENSHOT_DIR");
        if (directory.isEmpty())
            return;
        QVERIFY(QDir().mkpath(directory));
        fc::Config config;
        fc::Alarm alarm;
        alarm.label = QStringLiteral("休息提醒");
        alarm.content = QStringLiteral("起身活动，喝杯水。这个提醒会在 60 秒后自动停止。");
        config.alarms = {alarm};
        fc::SettingsDialog settings(config, fc::Capabilities());
        settings.show();
        QApplication::processEvents();
        QVERIFY(settings.grab().save(directory + "/settings.png"));
        FakeTime time;
        fc::Timers timers(time);
        timers.startCountdown(300000);
        fc::ControlPanel panel(timers, true);
        panel.show();
        QApplication::processEvents();
        QVERIFY(panel.grab().save(directory + "/control.png"));
        fc::AboutDialog about;
        about.show();
        QApplication::processEvents();
        QVERIFY(about.grab().save(directory + "/licenses.png"));
        fc::ClockWindow window;
        window.applyConfig(config);
        window.setDisplay("08:00:00", "08:00:00");
        window.setReminder(alarm.label, alarm.content);
        window.show();
        QApplication::processEvents();
        QVERIFY(window.grab().save(directory + "/reminder.png"));
        config.popupFlash = false;
        config.popupLayout = "label_only";
        config.fontSize = 24;
        config.popupFontScale = 1;
        window.applyConfig(config);
        window.setReminder(alarm.label, QStringLiteral("起身活动，喝杯水。"));
        QApplication::processEvents();
        QVERIFY(window.grab().save(directory + "/reminder-short.png"));
        config.fontSize = 8;
        window.applyConfig(config);
        window.setReminder(QStringLiteral("提醒"), QString());
        QApplication::processEvents();
        QVERIFY(window.grab().save(directory + "/reminder-small.png"));
        config.fontSize = 24;
        window.applyConfig(config);
        window.setReminder(alarm.label, alarm.content.repeated(2));
        QApplication::processEvents();
        QVERIFY(window.grab().save(directory + "/reminder-wrapped.png"));
        window.setReminder(alarm.label, (alarm.content + '\n').repeated(30));
        QApplication::processEvents();
        QVERIFY(window.grab().save(directory + "/reminder-long.png"));
    }
    void noTrayRetainsControlUntilQuit() {
        FakeTime time;
        fc::Timers timers(time);
        fc::ControlPanel panel(timers, false);
        QSignalSpy quit(&panel, &fc::ControlPanel::quitRequested);
        panel.show();
        QTest::keyClick(&panel, Qt::Key_Escape);
        QCOMPARE(quit.size(), 1);
        QVERIFY(panel.isVisible());
        panel.close();
        QCOMPARE(quit.size(), 2);
        QVERIFY(panel.isVisible());
        panel.setTrayAvailable(true);
        QTest::keyClick(&panel, Qt::Key_Escape);
        QCOMPARE(quit.size(), 2);
        QVERIFY(!panel.isVisible());
    }
    void silentAndFailedSoundStillExpire_data() {
        QTest::addColumn<bool>("unavailable");
        QTest::newRow("silent") << false;
        QTest::newRow("audio failure") << true;
    }
    void silentAndFailedSoundStillExpire() {
        QFETCH(bool, unavailable);
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        sound.unavailable = unavailable;
        fc::ApplicationController controller(store, time, platform, sound, false);
        controller.config().soundMode = unavailable ? "system" : "silent";
        controller.config().alarmTimeoutSeconds = 1;
        fc::Alarm alarm;
        alarm.time = "07:59";
        controller.config().alarms.append(alarm);
        controller.tick();
        QVERIFY(controller.clock().reminderVisible());
        QVERIFY(!sound.audible);
        time.advance(1000);
        controller.tick();
        QVERIFY(!controller.reminders().active());
        QVERIFY(!controller.clock().reminderVisible());
        QVERIFY(platform.through);
        QVERIFY(sound.stops > 0);
    }
    void appRingingTimeoutAndPreferences() {
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        fc::ApplicationController controller(store, time, platform, sound, false);
        QVERIFY(platform.through);
        controller.setMoveMode(true);
        QVERIFY(!platform.through);
        QVERIFY(controller.config().clickThrough);
        controller.setMoveMode(false);
        fc::Alarm alarm;
        alarm.repeat = "once";
        alarm.timeoutSeconds = 1;
        controller.config().alarms = {alarm};
        time.wall = time.wall.addSecs(60);
        controller.tick();
        QVERIFY(controller.reminders().active());
        QVERIFY(!platform.through);
        QCOMPARE(sound.plays, 1);
        QVERIFY(!store.load().alarms.first().enabled);
        time.advance(1000);
        controller.tick();
        QVERIFY(!controller.reminders().active());
        QVERIFY(!controller.clock().reminderVisible());
        QVERIFY(platform.through);
        QVERIFY(controller.config().clickThrough);
        QCOMPARE(platform.startupWrites, 0);
    }
    void appScreenOffAndWake() {
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        fc::ApplicationController controller(store, time, platform, sound, false);
        fc::Alarm alarm;
        alarm.repeat = "once";
        controller.config().alarms = {alarm};
        platform.state = fc::DisplayState::Off;
        time.wall = time.wall.addSecs(60);
        controller.tick();
        QVERIFY(controller.config().alarms[0].enabled);
        QCOMPARE(sound.plays, 0);
        platform.state = fc::DisplayState::Unknown;
        controller.tick();
        QCOMPARE(sound.plays, 1);
        time.advance(60001);
        platform.wake();
        QVERIFY(!controller.reminders().active());
        QVERIFY(platform.through);
    }
    void appCountdownDuringSleep() {
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        fc::ApplicationController controller(store, time, platform, sound, false);
        controller.timers().startCountdown(1000);
        time.advance(2000);
        platform.wake();
        QCOMPARE(controller.timers().countdownState(), fc::Timers::State::Finished);
        QVERIFY(!controller.reminders().active());
        QCOMPARE(sound.plays, 0);
        controller.timers().startCountdown(1000);
        time.advance(1000);
        controller.tick();
        QVERIFY(controller.reminders().active());
        QCOMPARE(sound.plays, 1);
    }
    void appNewAlarmDoesNotExtendOld() {
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        fc::ApplicationController controller(store, time, platform, sound, false);
        fc::Alarm first;
        first.time = "07:59";
        first.timeoutSeconds = 1;
        controller.config().alarms.append(first);
        controller.tick();
        time.advance(500);
        fc::Alarm second = first;
        second.id = "second";
        second.timeoutSeconds = 3;
        controller.config().alarms.append(second);
        controller.tick();
        QCOMPARE(controller.reminders().items().size(), 2);
        time.advance(500);
        controller.tick();
        QCOMPARE(controller.reminders().items().size(), 1);
        QCOMPARE(sound.plays, 1);
        controller.stopReminders();
        QVERIFY(platform.through);
        controller.config().clickThrough = false;
        controller.applyClickThrough();
        controller.stopReminders();
        QVERIFY(!platform.through);
    }
    void appMergedReminderSoundEligibility_data() {
        QTest::addColumn<bool>("firstAudible");
        QTest::newRow("audible then silent") << true;
        QTest::newRow("silent then audible") << false;
    }
    void appMergedReminderSoundEligibility() {
        QFETCH(bool, firstAudible);
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        fc::ApplicationController controller(store, time, platform, sound, false);
        fc::Alarm first;
        first.time = "07:59";
        first.timeoutSeconds = 1;
        controller.config().soundMode = firstAudible ? "system" : "silent";
        controller.config().alarms.append(first);
        controller.tick();
        QCOMPARE(sound.audible, firstAudible);
        time.advance(500);
        auto second = first;
        second.id = "second";
        second.timeoutSeconds = 3;
        controller.config().soundMode = firstAudible ? "silent" : "system";
        controller.config().alarms.append(second);
        controller.tick();
        QVERIFY(sound.audible);
        time.advance(500);
        controller.tick();
        QCOMPARE(controller.reminders().items().size(), 1);
        QVERIFY(controller.clock().reminderVisible());
        QCOMPARE(sound.audible, !firstAudible);
        QCOMPARE(sound.plays, 1);
        QVERIFY(!platform.through);
        time.advance(2500);
        controller.tick();
        QVERIFY(!sound.audible);
        QVERIFY(!controller.clock().reminderVisible());
        QVERIFY(platform.through);
    }
    void appMergedReminderSoundSnapshot() {
        QTemporaryDir directory;
        fc::ConfigStore store(directory.filePath("config.ini"));
        FakeTime time;
        FakePlatform platform;
        FakeSound sound;
        fc::ApplicationController controller(store, time, platform, sound, false);
        fc::Alarm first;
        first.time = "07:59";
        first.timeoutSeconds = 1;
        controller.config().soundMode = "custom";
        controller.config().soundPath = "first.wav";
        controller.config().alarms.append(first);
        controller.tick();
        QCOMPARE(sound.path, QString("first.wav"));
        time.advance(500);
        auto second = first;
        second.id = "second";
        second.timeoutSeconds = 3;
        controller.config().soundPath = "second.wav";
        controller.config().alarms.append(second);
        controller.tick();
        QCOMPARE(sound.plays, 1);
        controller.config().soundPath = "later-edit.wav";
        time.advance(500);
        controller.tick();
        QCOMPARE(sound.plays, 2);
        QCOMPARE(sound.path, QString("second.wav"));
    }
    void singleInstanceIsolation() {
        QTemporaryDir directory;
        fc::SingleInstance first(directory.filePath("one/config.ini"));
        fc::SingleInstance same(directory.filePath("one/other.ini"));
        fc::SingleInstance different(directory.filePath("two/config.ini"));
        QCOMPARE(first.name(), same.name());
        QVERIFY(first.name() != different.name());
        QString error;
        QCOMPARE(first.start(&error), fc::SingleInstance::Result::Primary);
        QCOMPARE(different.start(&error), fc::SingleInstance::Result::Primary);
        QCOMPARE(same.start(&error), fc::SingleInstance::Result::ActivatedExisting);
    }
};
} // namespace

int main(int argc, char **argv) {
#ifdef Q_OS_WIN
    if (qEnvironmentVariableIsEmpty("QT_QPA_FONTDIR"))
        qputenv("QT_QPA_FONTDIR", qgetenv("WINDIR") + "/Fonts");
#endif
    QApplication application(argc, argv);
    application.setQuitOnLastWindowClosed(false);
    ClockTests tests;
    return QTest::qExec(&tests, argc, argv);
}
#include "tests.moc"
