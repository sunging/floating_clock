#include "ui/translation.h"
#include "core/i18n.h"

#include <QComboBox>
#include <QFormLayout>
#include <QLabel>
#include <QSignalBlocker>
#include <QTabWidget>
#include <QVariant>

namespace fc {

void bindTranslation(QObject *context, const std::function<void()> &update) {
    QObject::connect(&LanguageManager::instance(), &LanguageManager::changed, context, update);
    update();
}

void bindText(QObject *object, const char *source, const char *property) {
    bindTranslation(
        object, [object, source, property] { object->setProperty(property, I18n::tr(source)); });
}

void addTranslatedRow(QFormLayout *form, const char *source, QWidget *field) {
    auto *label = new QLabel;
    label->setBuddy(field);
    bindText(label, source);
    form->addRow(label, field);
}

void addTranslatedItem(QComboBox *combo, const char *source, const QString &value) {
    const int index = combo->count();
    combo->addItem(QString(), value);
    bindTranslation(combo, [combo, source, index] {
        const QSignalBlocker block(combo);
        combo->setItemText(index, I18n::tr(source));
    });
}

void addTranslatedTab(QTabWidget *tabs, QWidget *page, const char *source) {
    tabs->addTab(page, QString());
    bindTranslation(
        tabs, [tabs, page, source] { tabs->setTabText(tabs->indexOf(page), I18n::tr(source)); });
}

} // namespace fc
