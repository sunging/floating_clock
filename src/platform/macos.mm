#include "platform/services.h"

#import <AppKit/AppKit.h>
#import <CoreGraphics/CoreGraphics.h>
#include <QCoreApplication>
#include <QDir>
#include <QFile>
#include <QFileInfo>
#include <QPointer>
#include <QSaveFile>
#include <QXmlStreamWriter>

namespace fc {
namespace {
QString agentPath() {
    return QDir::homePath() + "/Library/LaunchAgents/com.sunging.floating-clock.plist";
}

class MacPlatform final : public PlatformServices {
public:
    ~MacPlatform() override {
        for (id observer in observers_)
            [[[NSWorkspace sharedWorkspace] notificationCenter] removeObserver:observer];
    }

    void start(QWidget *window) override {
        Q_UNUSED(window)
        capabilities_.displayPower = true;
        NSNotificationCenter *center = [[NSWorkspace sharedWorkspace] notificationCenter];
        auto observe = [&](NSNotificationName name, void (^callback)(NSNotification *)) {
            id token = [center addObserverForName:name
                                           object:nil
                                            queue:[NSOperationQueue mainQueue]
                                       usingBlock:callback];
            [observers_ addObject:token];
        };
        const QPointer<MacPlatform> weak(this);
        observe(NSWorkspaceScreensDidSleepNotification, ^(NSNotification *notification) {
          Q_UNUSED(notification)
          if (weak)
              weak->displayState_ = DisplayState::Off;
        });
        observe(NSWorkspaceScreensDidWakeNotification, ^(NSNotification *notification) {
          Q_UNUSED(notification)
          if (weak) {
              weak->displayState_ = DisplayState::On;
              emit weak->waking();
          }
        });
        observe(NSWorkspaceWillSleepNotification, ^(NSNotification *notification) {
          Q_UNUSED(notification)
          if (weak)
              emit weak->sleeping();
        });
        observe(NSWorkspaceDidWakeNotification, ^(NSNotification *notification) {
          Q_UNUSED(notification)
          if (weak)
              emit weak->waking();
        });
    }

    Capabilities capabilities() const override {
        auto result = capabilities_;
        if (!CGPreflightScreenCaptureAccess())
            result.explanation =
                QStringLiteral("自动取色需要屏幕录制权限；可在启用时授权，拒绝后使用固定颜色。");
        return result;
    }

    bool requestScreenSampling() override {
        return CGPreflightScreenCaptureAccess() || CGRequestScreenCaptureAccess();
    }

    void setClickThrough(QWidget *window, bool enabled) override {
        if (!capabilities_.clickThrough)
            return;
        NSView *view = (__bridge NSView *)(reinterpret_cast<void *>(window->winId()));
        [[view window] setIgnoresMouseEvents:enabled];
    }

    bool autostartEnabled() const override {
        return QFileInfo::exists(agentPath());
    }

    bool setAutostart(bool enabled, const QString &config, QString *error) override {
        if (!enabled) {
            if (!QFileInfo::exists(agentPath()) || QFile::remove(agentPath()))
                return true;
        } else {
            QByteArray bytes;
            QXmlStreamWriter xml(&bytes);
            xml.setAutoFormatting(true);
            xml.writeStartDocument();
            xml.writeDTD("<!DOCTYPE plist PUBLIC \"-//Apple//DTD PLIST 1.0//EN\" "
                         "\"http://www.apple.com/DTDs/PropertyList-1.0.dtd\">");
            xml.writeStartElement("plist");
            xml.writeAttribute("version", "1.0");
            xml.writeStartElement("dict");
            xml.writeTextElement("key", "Label");
            xml.writeTextElement("string", "com.sunging.floating-clock");
            xml.writeTextElement("key", "ProgramArguments");
            xml.writeStartElement("array");
            for (const auto &argument :
                 QStringList{QCoreApplication::applicationFilePath(), "--config", config})
                xml.writeTextElement("string", argument);
            xml.writeEndElement();
            xml.writeTextElement("key", "RunAtLoad");
            xml.writeEmptyElement("true");
            xml.writeTextElement("key", "ProcessType");
            xml.writeTextElement("string", "Interactive");
            xml.writeEndElement();
            xml.writeEndElement();
            xml.writeEndDocument();
            QSaveFile file(agentPath());
            if (QDir().mkpath(QFileInfo(agentPath()).absolutePath()) &&
                file.open(QIODevice::WriteOnly) && file.write(bytes) == bytes.size() &&
                file.commit())
                return true;
        }
        if (error)
            *error = QStringLiteral("无法保存登录启动设置。请检查 LaunchAgents 目录权限。");
        return false;
    }

private:
    NSMutableArray *observers_ = [NSMutableArray array];
};
} // namespace

std::unique_ptr<PlatformServices> makePlatformServices() {
    return std::make_unique<MacPlatform>();
}

} // namespace fc
