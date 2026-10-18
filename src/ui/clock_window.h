#pragma once

#include "core/model.h"
#include <QImage>
#include <QLabel>
#include <QPlainTextEdit>
#include <QPushButton>
#include <QTimer>
#include <QWidget>
#include <functional>

namespace fc {

QRect screenAreaFor(const QRect &window, const QList<QRect> &screens, const QRect &fallback);
QPoint clampedPosition(const QRect &window, const QRect &area);

class ClockWindow : public QWidget {
    Q_OBJECT
public:
    using BackgroundSampler = std::function<QImage(const QRect &)>;
    explicit ClockWindow(QWidget *parent = nullptr, BackgroundSampler sampler = {});
    void applyConfig(const Config &config);
    void setDisplay(const QString &text, const QString &clockTime);
    void setReminder(const QString &title, const QString &content);
    void clearReminder();
    void setMoveHint(bool enabled);
    void setInteractive(bool enabled);
    void restorePosition();
    void sampleBackground();
    bool isDragging() const;
    bool reminderVisible() const;
    static QString formattedClock(const Config &config, const QDateTime &now);

signals:
    void moved(const QPoint &position);
    void dismissed();
    void controlRequested();

protected:
    void paintEvent(QPaintEvent *event) override;
    bool eventFilter(QObject *watched, QEvent *event) override;
    void mousePressEvent(QMouseEvent *event) override;
    void mouseMoveEvent(QMouseEvent *event) override;
    void mouseReleaseEvent(QMouseEvent *event) override;
    void contextMenuEvent(QContextMenuEvent *event) override;

private:
    void render();
    void fit();
    QRect area() const;
    Config config_;
    BackgroundSampler sampler_;
    QLabel *label_;
    QWidget *panel_;
    QPlainTextEdit *text_;
    QPushButton *stop_;
    QTimer flash_;
    QString display_;
    QString clockTime_;
    QString title_;
    QString content_;
    QString autoColor_;
    bool reminder_ = false;
    bool phase_ = false;
    bool moveHint_ = false;
    bool interactive_ = true;
    bool dragging_ = false;
    bool moved_ = false;
    QPoint dragOffset_;
    QPoint pressPosition_;
};

} // namespace fc
