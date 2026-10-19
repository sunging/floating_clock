qtbase_zh_CN.ts is the unmodified Qt v6.12.0 translation catalog.
Source: https://github.com/qt/qttranslations/blob/v6.12.0/translations/qtbase_zh_CN.ts
SHA256: e63a70eedd900438ec1c63877c525bcda5c8292803bf0e228995de09fb9ddeb7
Qt copyright and license terms apply; see THIRD_PARTY_NOTICES.md and resources/licenses.
The static SDK recipe runs the matching lrelease to create qtbase_zh_CN.qm.

Application translations
------------------------
floating-clock_zh_CN.ts is the application's English-source Simplified Chinese catalog.
English uses the source strings and requires no separate QM file. Meson's Qt module compiles
application.qrc and embeds the Chinese QM into every executable, including standalone Windows.

Use fc::I18n::tr() for generated text and QT_TRANSLATE_NOOP("FloatingClock", "English source")
with the bindings in src/ui/translation.h for fixed widget text. Keep names, notes and paths
entered by the user outside translation lookups. Preserve %1, %2 and %n placeholders.

Check coverage, completion and placeholder consistency with:
  python scripts/check_translations.py

With Qt Linguist lupdate and its required QML runtime installed, refresh catalog sources using:
  lupdate src -I src -no-obsolete -locations none -source-language en -target-language zh_CN -ts resources/translations/floating-clock_zh_CN.ts

Review and complete the Chinese translations before building. Regular compilation only needs
lrelease; it does not require lupdate, QML libraries or Python at application runtime.
