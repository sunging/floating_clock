"""Guard application catalog coverage and runtime formatting placeholders."""

import importlib.util
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("check_translations", ROOT / "scripts/check_translations.py")
translations = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(translations)


class TranslationTests(unittest.TestCase):
    def test_catalog_covers_all_application_messages(self):
        sources = translations.collect_sources()
        self.assertIn("Stop reminders", sources)
        self.assertIn("%n reminders", sources)
        self.assertEqual(translations.validate_catalog(expected=sources), [])

    def test_missing_placeholder_or_unfinished_translation_is_rejected(self):
        for translation in [
            "<translation>Saved</translation>",
            '<translation type="unfinished">%1</translation>',
        ]:
            with self.subTest(translation=translation), tempfile.TemporaryDirectory() as folder:
                path = Path(folder) / "fixture.ts"
                path.write_text(
                    '<TS language="zh_CN" sourcelanguage="en"><context><name>FloatingClock</name>'
                    "<message><source>Saved %1</source>" + translation + "</message></context></TS>",
                    encoding="utf-8",
                )
                self.assertTrue(translations.validate_catalog(path, expected={"Saved %1"}))

    def test_source_collection_handles_multiline_literals(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "src").mkdir()
            (root / "src/example.cpp").write_text(
                'I18n::tr("Line one "\n"and two %1");\n'
                'QT_TRANSLATE_NOOP("FloatingClock", "Fixed label");\n'
                "I18n::tr(userData);\n",
                encoding="utf-8",
            )
            self.assertEqual(translations.collect_sources(root), {"Line one and two %1", "Fixed label"})


if __name__ == "__main__":
    unittest.main()
