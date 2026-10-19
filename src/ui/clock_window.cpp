#include "ui/clock_window.h"
#include "core/i18n.h"
#include "platform/services.h"
#include "ui/translation.h"

#include <QApplication>
#include <QColor>
#include <QContextMenuEvent>
#include <QFontMetricsF>
#include <QGuiApplication>
#include <QMenu>
#include <QMouseEvent>
#include <QPainter>
#include <QScreen>
#include <QScrollBar>
#include <QTextBlock>
#include <QTextDocument>
#include <QTextLayout>
#include <QVBoxLayout>
#include <QWindow>
#include <algorithm>
#include <cmath>

namespace fc {

namespace {
int reminderTextHeight(const QPlainTextEdit *text, int width, int limit) {
    const auto *document = text->document();
    const qreal margin = document->documentMargin();
    // QPlainTextEdit reserves one extra pixel when deciding whether the last line fits.
    qreal height = 2 * margin + 1;
    // Match QPlainTextEdit's wrapping and line leading instead of estimating a rich-text height.
    for (auto block = document->begin(); block.isValid(); block = block.next()) {
        QTextLayout paragraph(block.text(), text->font(), text->viewport());
        paragraph.setTextOption(document->defaultTextOption());
        paragraph.beginLayout();
        while (true) {
            auto line = paragraph.createLine();
            if (!line.isValid())
                break;
            line.setLeadingIncluded(true);
            line.setLineWidth(std::max(qreal(1), width - 2 * margin));
            height += line.height();
            if (line.leading() < 0)
                height += std::ceil(line.leading());
            if (height >= limit)
                break;
        }
        paragraph.endLayout();
        if (height >= limit)
            return limit;
    }
    return std::min(limit, int(std::ceil(height)));
}
} // namespace

QRect screenAreaFor(const QRect &window, const QList<QRect> &screens, const QRect &fallback) {
    QRect best = fallback;
    qint64 bestSize = 0;
    for (const auto &candidate : screens) {
        if (candidate.contains(window.center()))
            return candidate;
        const auto intersection = window.intersected(candidate);
        const qint64 size = qint64(intersection.width()) * intersection.height();
        if (size > bestSize) {
            bestSize = size;
            best = candidate;
        }
    }
    return best;
}

QPoint clampedPosition(const QRect &window, const QRect &area) {
    const int right = std::max(area.left(), area.right() - window.width() + 1);
    const int bottom = std::max(area.top(), area.bottom() - window.height() + 1);
    return {std::clamp(window.x(), area.left(), right), std::clamp(window.y(), area.top(), bottom)};
}

ClockWindow::ClockWindow(QWidget *parent, BackgroundSampler sampler)
    : QWidget(parent), sampler_(sampler ? std::move(sampler) : captureScreenRegion) {
    bindText(this, QT_TRANSLATE_NOOP("FloatingClock", "Floating Clock"), "windowTitle");
    setWindowFlags(Qt::FramelessWindowHint | Qt::WindowStaysOnTopHint | Qt::Tool);
    setAttribute(Qt::WA_TranslucentBackground);
    auto *layout = new QVBoxLayout(this);
    layout->setContentsMargins(8, 8, 8, 8);
    layout->setSizeConstraint(QLayout::SetNoConstraint);
    label_ = new QLabel(this);
    label_->setAlignment(Qt::AlignCenter);
    label_->setTextFormat(Qt::PlainText);
    label_->setAttribute(Qt::WA_TransparentForMouseEvents);
    layout->addWidget(label_);
    panel_ = new QWidget(this);
    panel_->setObjectName("reminderPanel");
    auto *popup = new QVBoxLayout(panel_);
    popup->setContentsMargins(8, 8, 8, 8);
    popup->setSpacing(6);
    text_ = new QPlainTextEdit(panel_);
    text_->setObjectName("reminderText");
    text_->setReadOnly(true);
    text_->setTextInteractionFlags(Qt::NoTextInteraction);
    text_->setFrameShape(QFrame::NoFrame);
    text_->setWordWrapMode(QTextOption::WrapAtWordBoundaryOrAnywhere);
    text_->setHorizontalScrollBarPolicy(Qt::ScrollBarAlwaysOff);
    text_->setSizePolicy(QSizePolicy::Expanding, QSizePolicy::Ignored);
    text_->setMinimumSize(0, 0);
    text_->viewport()->installEventFilter(this);
    popup->addWidget(text_, 1);
    stop_ =
        translatedWidget<QPushButton>(QT_TRANSLATE_NOOP("FloatingClock", "Stop reminders"), panel_);
    stop_->setObjectName("stopReminder");
    connect(stop_, &QPushButton::clicked, this, &ClockWindow::dismissed);
    popup->addWidget(stop_);
    layout->addWidget(panel_);
    panel_->hide();
    flash_.setInterval(450);
    connect(&flash_, &QTimer::timeout, this, [this] {
        phase_ = !phase_;
        render();
    });
    applyConfig(Config());
    connect(&LanguageManager::instance(), &LanguageManager::changed, this, [this] { render(); });
}

void ClockWindow::applyConfig(const Config &config) {
    config_ = config;
    if (!config_.autoColor)
        autoColor_.clear();
    setWindowOpacity(config.opacity);
    if (reminder_ && config.popupFlash)
        flash_.start();
    else
        flash_.stop();
    render();
    if (!dragging_)
        restorePosition();
    if (isVisible())
        sampleBackground();
}

QString ClockWindow::formattedClock(const Config &config, const QDateTime &now) {
    QString text = now.time().toString(config.showSeconds ? "HH:mm:ss" : "HH:mm");
    if (config.showDate)
        text += '\n' + now.date().toString("yyyy-MM-dd");
    return text;
}

void ClockWindow::setDisplay(const QString &text, const QString &clockTime) {
    if (display_ == text && clockTime_ == clockTime)
        return;
    const bool repaint = reminder_ ? clockTime_ != clockTime : display_ != text;
    display_ = text;
    clockTime_ = clockTime;
    if (repaint)
        render();
}

void ClockWindow::setReminder(const QString &title, const QString &content) {
    const bool wasActive = reminder_;
    reminder_ = true;
    title_ = title;
    content_ = content;
    if (!wasActive) {
        phase_ = false;
        if (config_.popupFlash)
            flash_.start();
    }
    render();
}

void ClockWindow::clearReminder() {
    reminder_ = false;
    flash_.stop();
    render();
    restorePosition();
}

void ClockWindow::setMoveHint(bool enabled) {
    moveHint_ = enabled;
    render();
}

void ClockWindow::setInteractive(bool enabled) {
    if (interactive_ == enabled)
        return;
    interactive_ = enabled;
    update();
}

void ClockWindow::paintEvent(QPaintEvent *event) {
    Q_UNUSED(event)
    if (!interactive_)
        return;
    // Windows ignores alpha-zero pixels during layered-window hit testing.
    // Keep an almost invisible input surface even at the lowest supported opacity.
    QPainter painter(this);
    const int alpha = int(std::ceil(2.0 / std::max(0.1, windowOpacity())));
    painter.fillRect(rect(), QColor(0, 0, 0, alpha));
}

QRect ClockWindow::area() const {
    QList<QRect> areas;
    for (auto *screen : QGuiApplication::screens())
        areas.append(screen->availableGeometry());
    const auto *primary = QGuiApplication::primaryScreen();
    return screenAreaFor(frameGeometry(), areas,
                         primary ? primary->availableGeometry() : QRect(0, 0, 800, 600));
}

void ClockWindow::restorePosition() {
    if (dragging_ || QGuiApplication::platformName().startsWith("wayland"))
        return;
    QPoint desired = pos();
    if (config_.posX && config_.posY)
        desired = {*config_.posX, *config_.posY};
    const QRect target(desired, size());
    QList<QRect> areas;
    for (auto *screen : QGuiApplication::screens())
        areas.append(screen->availableGeometry());
    move(clampedPosition(target, screenAreaFor(target, areas, area())));
    fit();
}

void ClockWindow::render() {
    label_->setVisible(!reminder_);
    panel_->setVisible(reminder_);
    if (reminder_) {
        QString text = title_ + (content_.isEmpty() ? QString() : '\n' + content_);
        if (config_.popupLayout == "time_label")
            text = clockTime_ + '\n' + text;
        else if (config_.popupLayout != "label_only")
            text += '\n' + clockTime_;
        if (text_->toPlainText() != text) {
            auto *scroll = text_->verticalScrollBar();
            const int previous = scroll->value();
            const bool atBottom = previous > 0 && previous == scroll->maximum();
            text_->setPlainText(text);
            fit();
            scroll->setValue(atBottom ? scroll->maximum() : previous);
        }
        QColor bg(config_.popupBackgroundColor);
        bg.setAlphaF(config_.popupOpacity);
        QColor foreground(config_.popupTextColor);
        if (config_.popupFlash && phase_)
            foreground.setAlphaF(0.35);
        panel_->setStyleSheet(
            QStringLiteral("#reminderPanel { background: %1; border-radius: 8px; }")
                .arg(bg.name(QColor::HexArgb)));
        text_->setStyleSheet(
            QStringLiteral("QPlainTextEdit { background: transparent; color: %1; }")
                .arg(foreground.name(QColor::HexArgb)));
    } else {
        label_->setText(display_);
        const auto color = config_.autoColor && !autoColor_.isEmpty() ? autoColor_ : config_.color;
        label_->setStyleSheet(QStringLiteral("color: %1; background: transparent; border: %2;")
                                  .arg(color, moveHint_ ? "1px dashed #2D6CDF" : "none"));
    }
    fit();
}

void ClockWindow::fit() {
    const auto bounds = area();
    const int maxWidth = std::max(80, int(bounds.width() * 0.8));
    const int maxHeight = std::max(80, int(bounds.height() * 0.8));
    if (reminder_) {
        const int fontSize = std::clamp(int(config_.fontSize * config_.popupFontScale), 8, 400);
        QFont font(QStringLiteral("Arial"));
        font.setPointSize(std::min(fontSize, std::max(8, maxHeight / 6)));
        text_->setFont(font);
        const auto outer = layout()->contentsMargins();
        const auto inner = panel_->layout()->contentsMargins();
        const int horizontalPadding = outer.left() + outer.right() + inner.left() + inner.right();
        const int verticalPadding = outer.top() + outer.bottom() + inner.top() + inner.bottom() +
                                    panel_->layout()->spacing() + stop_->sizeHint().height();
        const QFontMetricsF metrics(font, text_->viewport());
        qreal width = std::max(200, stop_->sizeHint().width() + horizontalPadding);
        for (const auto &line : text_->toPlainText().split('\n'))
            width =
                std::max(width, metrics.horizontalAdvance(line) +
                                    2 * text_->document()->documentMargin() + horizontalPadding);
        const int wantedWidth = std::min(maxWidth, int(std::ceil(width)));
        const int availableTextHeight = std::max(1, maxHeight - verticalPadding);
        const int textHeight =
            reminderTextHeight(text_, wantedWidth - horizontalPadding, availableTextHeight);
        // An old scrollbar must not narrow a newly fitted document and create extra wrapped lines.
        text_->setVerticalScrollBarPolicy(textHeight < availableTextHeight ? Qt::ScrollBarAlwaysOff
                                                                           : Qt::ScrollBarAsNeeded);
        resize(wantedWidth, std::min(maxHeight, textHeight + verticalPadding));
    } else {
        QFont font(QStringLiteral("Arial"));
        font.setPointSize(config_.fontSize);
        const auto measure = [&](const QFont &f) {
            return QFontMetricsF(f)
                .boundingRect(QRectF(0, 0, 100000, 100000), Qt::AlignCenter,
                              display_.isEmpty() ? "00:00:00" : display_)
                .size();
        };
        QSizeF size = measure(font);
        const double scale = std::min({1.0, (maxWidth - 20) / std::max(1.0, size.width()),
                                       (maxHeight - 20) / std::max(1.0, size.height())});
        font.setPointSizeF(std::max(6.0, config_.fontSize * scale));
        label_->setFont(font);
        size = measure(font);
        resize(std::min(maxWidth, int(std::ceil(size.width())) + 20),
               std::min(maxHeight, int(std::ceil(size.height())) + 20));
    }
    if (!dragging_ && !QGuiApplication::platformName().startsWith("wayland"))
        move(clampedPosition(frameGeometry(), bounds));
}

void ClockWindow::sampleBackground() {
    if (!config_.autoColor || reminder_ || QGuiApplication::platformName().startsWith("wayland"))
        return;
    const auto background = sampler_(frameGeometry());
    if (background.isNull())
        return;
    const auto image = background.scaled(8, 8, Qt::IgnoreAspectRatio, Qt::SmoothTransformation);
    QVector<double> luminances;
    for (int y = 0; y < image.height(); ++y)
        for (int x = 0; x < image.width(); ++x) {
            const auto color = image.pixelColor(x, y);
            luminances.append(0.299 * color.red() + 0.587 * color.green() + 0.114 * color.blue());
        }
    std::sort(luminances.begin(), luminances.end());
    const auto color = luminances.at(luminances.size() / 2) > 140 ? config_.lightBackgroundColor
                                                                  : config_.darkBackgroundColor;
    if (autoColor_ == color)
        return;
    autoColor_ = color;
    render();
}

bool ClockWindow::isDragging() const {
    return dragging_;
}

bool ClockWindow::reminderVisible() const {
    return reminder_;
}

bool ClockWindow::eventFilter(QObject *watched, QEvent *event) {
    if (watched == text_->viewport() && event->type() == QEvent::MouseButtonRelease &&
        static_cast<QMouseEvent *>(event)->button() == Qt::LeftButton) {
        emit dismissed();
        return true;
    }
    return QWidget::eventFilter(watched, event);
}

void ClockWindow::mousePressEvent(QMouseEvent *event) {
    if (event->button() == Qt::LeftButton) {
        dragging_ = true;
        moved_ = false;
        pressPosition_ = event->globalPosition().toPoint();
        dragOffset_ = pressPosition_ - frameGeometry().topLeft();
        event->accept();
    }
}

void ClockWindow::mouseMoveEvent(QMouseEvent *event) {
    if (!dragging_ || !(event->buttons() & Qt::LeftButton))
        return;
    const auto point = event->globalPosition().toPoint();
    if ((point - pressPosition_).manhattanLength() < QApplication::startDragDistance() && !moved_)
        return;
    if (QGuiApplication::platformName().startsWith("wayland")) {
        if (!moved_ && windowHandle())
            moved_ = windowHandle()->startSystemMove();
        return;
    }
    moved_ = true;
    move(point - dragOffset_);
    move(clampedPosition(frameGeometry(), area()));
}

void ClockWindow::mouseReleaseEvent(QMouseEvent *event) {
    if (event->button() != Qt::LeftButton || !dragging_)
        return;
    dragging_ = false;
    if (moved_)
        emit moved(pos());
    else if (reminder_)
        emit dismissed();
}

void ClockWindow::contextMenuEvent(QContextMenuEvent *event) {
    Q_UNUSED(event)
    emit controlRequested();
}

} // namespace fc
