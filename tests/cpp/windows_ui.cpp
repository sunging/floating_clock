#include "platform/services.h"
#include "ui/clock_window.h"

#include <QApplication>
#include <QMouseEvent>
#include <QScreen>
#include <QSignalSpy>
#include <QTest>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>

namespace {
class DesktopFixture {
public:
    DesktopFixture(int fontSize = 48, double opacity = .75) {
        background.setWindowFlags(Qt::Tool | Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint |
                                  Qt::WindowDoesNotAcceptFocus);
        background.setAttribute(Qt::WA_ShowWithoutActivating);
        const auto area = QGuiApplication::primaryScreen()->availableGeometry();
        background.setGeometry(QRect(area.center() - QPoint(320, 140), QSize(640, 280)));
        background.setStyleSheet("background: white;");
        background.show();
        config.posX = background.x() + 40;
        config.posY = background.y() + 40;
        config.clickThrough = false;
        config.autoColor = true;
        config.fontSize = fontSize;
        config.opacity = opacity;
        clock.setAttribute(Qt::WA_ShowWithoutActivating);
        clock.applyConfig(config);
        clock.setDisplay("08:08:08", "08:08:08");
        clock.show();
        clock.raise();
    }
    QWidget background;
    fc::Config config;
    fc::ClockWindow clock;
};

class WindowsUiTests : public QObject {
    Q_OBJECT
private slots:
    void initTestCase() {
        QCOMPARE(QGuiApplication::platformName(), QString("windows"));
    }
    void backgroundAdaptation_data() {
        QTest::addColumn<int>("fontSize");
        QTest::addColumn<double>("opacity");
        for (int fontSize : {8, 24, 48})
            for (double opacity : {.1, .4, .75, 1.0})
                QTest::newRow(
                    qUtf8Printable(QString::number(fontSize) + "/" + QString::number(opacity)))
                    << fontSize << opacity;
    }
    void backgroundAdaptation() {
        QFETCH(int, fontSize);
        QFETCH(double, opacity);
        DesktopFixture fixture(fontSize, opacity);
        QVERIFY(QTest::qWaitForWindowExposed(&fixture.background));
        QVERIFY(QTest::qWaitForWindowExposed(&fixture.clock));
        const auto *label = fixture.clock.findChild<QLabel *>();
        QVERIFY(label);
        const auto waitForColor = [&](const QString &color) {
            return QTest::qWaitFor(
                [&] {
                    fixture.clock.sampleBackground();
                    return label->styleSheet().contains(color);
                },
                3000);
        };
        QVERIFY2(waitForColor(fixture.config.lightBackgroundColor),
                 qPrintable(label->styleSheet()));
        fixture.background.setStyleSheet("background: black;");
        QVERIFY2(waitForColor(fixture.config.darkBackgroundColor), qPrintable(label->styleSheet()));
    }
    void interactiveClockHitTest_data() {
        QTest::addColumn<bool>("moveMode");
        QTest::addColumn<double>("opacity");
        for (bool moveMode : {false, true})
            for (double opacity : {.1, .75, 1.0})
                QTest::newRow(
                    qUtf8Printable(QString::number(moveMode) + "/" + QString::number(opacity)))
                    << moveMode << opacity;
    }
    void interactiveClockHitTest() {
        QFETCH(bool, moveMode);
        QFETCH(double, opacity);
        DesktopFixture fixture(48, opacity);
        fixture.clock.setMoveHint(moveMode);
        fc::PlatformServices platform;
        platform.setClickThrough(&fixture.clock, true);
        platform.setClickThrough(&fixture.clock, false);
        QVERIFY(QTest::qWaitForWindowExposed(&fixture.clock));
        const auto window = reinterpret_cast<HWND>(fixture.clock.winId());
        RECT bounds{};
        QVERIFY(GetWindowRect(window, &bounds));
        // Probe a transparent margin without moving the user's actual mouse pointer.
        const POINT point{bounds.left + 2, bounds.top + 2};
        QTRY_VERIFY2_WITH_TIMEOUT(
            GetAncestor(WindowFromPoint(point), GA_ROOT) == window,
            "Windows routes the clock's transparent margin to the window below", 3000);
        const QPoint start = fixture.clock.pos();
        const QPointF local(2, 2);
        const QPointF global = fixture.clock.mapToGlobal(local.toPoint());
        QMouseEvent press(QEvent::MouseButtonPress, local, global, Qt::LeftButton, Qt::LeftButton,
                          Qt::NoModifier);
        QApplication::sendEvent(&fixture.clock, &press);
        const QPoint offset(80, 30);
        QMouseEvent move(QEvent::MouseMove, local + offset, global + offset, Qt::NoButton,
                         Qt::LeftButton, Qt::NoModifier);
        QApplication::sendEvent(&fixture.clock, &move);
        QSignalSpy moved(&fixture.clock, &fc::ClockWindow::moved);
        QMouseEvent release(QEvent::MouseButtonRelease, local, global + offset, Qt::LeftButton,
                            Qt::NoButton, Qt::NoModifier);
        QApplication::sendEvent(&fixture.clock, &release);
        QCOMPARE(fixture.clock.pos(), start + offset);
        QCOMPARE(moved.size(), 1);
    }
};
} // namespace

int main(int argc, char **argv) {
    QApplication application(argc, argv);
    application.setQuitOnLastWindowClosed(false);
    WindowsUiTests tests;
    return QTest::qExec(&tests, argc, argv);
}

#include "windows_ui.moc"
