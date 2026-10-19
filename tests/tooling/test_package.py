"""Windows packaging must emit only the verified standalone executable."""

import importlib.util
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
SPEC = importlib.util.spec_from_file_location("package", ROOT / "scripts/package.py")
package = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package)


class WindowsPackageTests(unittest.TestCase):
    def test_smoke_checks_both_languages_with_isolated_configuration(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            executable = root / "application.exe"
            executable.touch()
            launched = []

            def launch(*arguments, **options):
                config = Path(arguments[arguments.index("--config") + 1])
                language = config.read_text(encoding="utf-8").split("language=")[1].strip()
                self.assertTrue(config.is_relative_to(root / "isolated"))
                self.assertEqual(options["cwd"], executable.parent)
                self.assertEqual(options["env"]["PATH"], os.path.join(os.environ["WINDIR"], "System32"))
                for key in ["QT_PLUGIN_PATH", "LD_LIBRARY_PATH", "DYLD_LIBRARY_PATH"]:
                    self.assertNotIn(key, options["env"])
                report = {
                    "version": package.VERSION,
                    "qt_version": "6.12.0",
                    "qt_linkage": "static",
                    "platform": "windows",
                    "language": language,
                    "application_translation_catalog": True,
                    "chinese_qt_translation": language == "zh_CN",
                    "embedded_translation": True,
                    "embedded_licenses": True,
                }
                config.with_name("state.json").write_text("{}")
                config.with_name("smoke-result.json").write_text(json.dumps(report))
                launched.append((language, config))

            with (
                patch.dict(os.environ, {"WINDIR": str(root / "Windows"), "QT_PLUGIN_PATH": "/isolated-sdk"}),
                patch.object(package, "run", side_effect=launch),
            ):
                package.smoke(executable, root / "isolated", "windows", linkage="static")
            self.assertEqual([language for language, _ in launched], ["en", "zh_CN"])
            self.assertNotEqual(launched[0][1], launched[1][1])

    def test_only_the_signed_standalone_executable_is_emitted_and_relocated(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            build, output, qt, work = [directory / name for name in ["build", "dist", "qt", "work"]]
            for path in [build / "src", output, qt, work, directory / "Windows/System32"]:
                path.mkdir(parents=True)
            (build / "src/floating-clock.exe").write_bytes(b"isolated executable fixture")
            (qt / "static-qt-build.json").write_text("{}")
            (directory / "Windows/System32/KERNEL32.dll").touch()
            signed = b"isolated signed executable fixture"
            launched = []

            def sign(executable, _work):
                executable.write_bytes(signed)

            def smoke(executable, _work, platform, *, linkage):
                self.assertEqual((platform, linkage), ("windows", "static"))
                self.assertEqual(list(executable.parent.iterdir()), [executable])
                self.assertEqual(executable.read_bytes(), signed)
                launched.append(executable)

            with (
                patch.dict(os.environ, {"WINDIR": str(directory / "Windows")}),
                patch.object(package.shutil, "which", return_value="strip"),
                patch.object(package, "run"),
                patch.object(package.subprocess, "check_output", return_value="DLL Name: KERNEL32.dll\n"),
                patch("signing.sign_windows", side_effect=sign),
                patch.object(package, "smoke", side_effect=smoke),
            ):
                artifacts = package.windows(build, output, qt, work)

            standalone = output / f"floating-clock-{package.VERSION}-windows-x64.exe"
            self.assertEqual(artifacts, [standalone])
            self.assertEqual(list(output.iterdir()), [standalone])
            self.assertEqual(standalone.read_bytes(), signed)
            self.assertEqual(len(launched), 2)
            self.assertEqual(launched[1].name, "浮动 时钟.exe")
            self.assertEqual(launched[1].parent.name, "单文件 启动验证")


if __name__ == "__main__":
    unittest.main()
