#pragma once

#include <QObject>
#include <functional>

class QComboBox;
class QFormLayout;
class QTabWidget;
class QWidget;

namespace fc {

void bindTranslation(QObject *context, const std::function<void()> &update);
void bindText(QObject *object, const char *source, const char *property = "text");
void addTranslatedRow(QFormLayout *form, const char *source, QWidget *field);
void addTranslatedItem(QComboBox *combo, const char *source, const QString &value);
void addTranslatedTab(QTabWidget *tabs, QWidget *page, const char *source);

template <typename Widget> Widget *translatedWidget(const char *source, QWidget *parent = nullptr) {
    auto *widget = new Widget(parent);
    bindText(widget, source);
    return widget;
}

} // namespace fc
