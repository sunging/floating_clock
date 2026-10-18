"""Static Qt links must include resource objects and relocatable private dependencies."""

import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("static_qt_link", ROOT / "scripts/static_qt_link.py")
linker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(linker)


class StaticQtLinkTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="qt sdk ")
        self.addCleanup(self.temporary.cleanup)
        self.prefix = Path(self.temporary.name).resolve()
        (self.prefix / "static-qt-build.json").write_text(
            json.dumps({"qt": "6.12.0", "static_compiler_runtime": True})
        )
        self.resource = self.prefix / "lib/objects-MinSizeRel/resource.obj"
        self.resource.parent.mkdir(parents=True)
        self.resource.write_bytes(b"resource")
        private = self.prefix / "lib/libQt6BundledZLIB.a"
        private.write_bytes(b"library")
        self.core_metadata = self.prefix / "lib/Qt6Core.prl"
        for relative in ["lib/Qt6Core.prl", *linker.PLUGINS]:
            metadata = self.prefix / relative
            metadata.parent.mkdir(parents=True, exist_ok=True)
            library = metadata.with_name("lib" + metadata.stem + ".a")
            library.write_bytes(b"library")
            metadata.write_text(
                f"QMAKE_PRL_TARGET = {library.name}\n"
                "QMAKE_PRL_CONFIG = static\nQMAKE_PRL_VERSION = 6.12.0\n"
                "QMAKE_PRL_LIBS_FOR_CMAKE = $$[QT_INSTALL_PREFIX]/lib/objects-MinSizeRel/resource.obj;"
                "$$[QT_INSTALL_LIBS]/libQt6BundledZLIB.a;-luser32\n"
            )

    def test_private_libraries_resources_and_spaces(self):
        flags = linker.link_arguments(self.prefix, ["Core"])
        self.assertEqual(flags[0], self.resource.as_posix())
        self.assertEqual(flags.count(self.resource.as_posix()), 1)
        self.assertEqual(flags.count("-luser32"), 1)
        self.assertIn((self.prefix / "lib/libQt6BundledZLIB.a").as_posix(), flags)
        self.assertIn("-Wl,--start-group", flags)
        self.assertEqual(flags[-1], "-Wl,--end-group")
        self.assertFalse(any("$$" in flag for flag in flags))

    def test_shared_or_missing_resources_rejected(self):
        original = self.core_metadata.read_text()
        self.core_metadata.write_text(original.replace("CONFIG = static", "CONFIG = shared"))
        with self.assertRaisesRegex(ValueError, "static Qt"):
            linker.link_arguments(self.prefix, ["Core"])
        self.core_metadata.write_text(original)
        self.resource.unlink()
        with self.assertRaisesRegex(ValueError, "missing"):
            linker.link_arguments(self.prefix, ["Core"])

    def test_unresolved_variables_and_outside_sdk_rejected(self):
        original = self.core_metadata.read_text()
        for replacement in ["$$[UNKNOWN]", self.prefix.parent.as_posix()]:
            self.core_metadata.write_text(original.replace("$$[QT_INSTALL_PREFIX]", replacement))
            with self.subTest(replacement=replacement), self.assertRaisesRegex(ValueError, "input"):
                linker.link_arguments(self.prefix, ["Core"])


if __name__ == "__main__":
    unittest.main()
