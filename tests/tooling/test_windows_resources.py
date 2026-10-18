"""Windows resource bundles must preserve notices and track SDK inputs in paths with spaces."""

import importlib.util
import json
import os
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

from mesonbuild.depfile import DepFile

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location(
    "windows_resources", ROOT / "scripts/embed_windows_resources.py"
)
resources = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(resources)


class WindowsResourcesTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix="single exe ")
        self.addCleanup(self.temporary.cleanup)
        self.directory = Path(self.temporary.name).resolve()
        self.qt = self.directory / "Qt SDK & notices"
        self.qt.mkdir()
        (self.qt / "static-qt-build.json").write_text(
            json.dumps({"qt": "6.12.0", "static_compiler_runtime": True})
        )
        for name, contents in {
            "translations/qtbase_zh_CN.qm": "isolated translation fixture",
            "LICENSES/Qt-license.txt": "Qt license fixture",
            "source-notices/attribution.json": "Qt third-party attribution fixture",
        }.items():
            path = self.qt / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(contents)
        self.compiler = self.directory / "compiler/bin/g++.exe"
        self.compiler.parent.mkdir(parents=True)
        self.compiler.touch()
        for name in ["gcc", "mingw-w64", "winpthreads"]:
            path = self.directory / "compiler/licenses" / name / "COPYING"
            path.parent.mkdir(parents=True)
            path.write_text(name + " runtime license fixture")
        self.output = self.directory / "构建 输出/bundle.qrc"

    def test_bundle_contains_translation_application_qt_and_runtime_notices(self):
        inputs = resources.generate_bundle(self.qt, self.output, static=True, compiler=self.compiler)
        entries = {
            entry.attrib["alias"]: Path(entry.text) for entry in ET.parse(self.output).findall(".//file")
        }
        self.assertEqual(set(entries), {"translations/qtbase_zh_CN.qm", "licenses/notices.txt"})
        self.assertEqual(entries["translations/qtbase_zh_CN.qm"], self.qt / "translations/qtbase_zh_CN.qm")
        notices = entries["licenses/notices.txt"].read_text(encoding="utf-8")
        self.assertNotIn(b"\r\n", entries["licenses/notices.txt"].read_bytes())
        for required in [
            "GNU AFFERO GENERAL PUBLIC LICENSE",
            "Qt license fixture",
            "Qt third-party attribution fixture",
            "winpthreads runtime license fixture",
            "static-qt-build.json",
        ]:
            self.assertIn(required, notices)
        self.assertIn(self.qt / "translations/qtbase_zh_CN.qm", inputs)

    def test_missing_translation_or_notices_rejected(self):
        translation = self.qt / "translations/qtbase_zh_CN.qm"
        translation.unlink()
        with self.assertRaisesRegex(ValueError, "translation"):
            resources.generate_bundle(self.qt, self.output, static=True, compiler=self.compiler)
        translation.write_bytes(b"translation")
        (self.qt / "source-notices/attribution.json").unlink()
        with self.assertRaisesRegex(ValueError, "notices are missing"):
            resources.generate_bundle(self.qt, self.output, static=True, compiler=self.compiler)

    def test_meson_depfile_tracks_escaped_source_paths(self):
        inputs = resources.generate_bundle(self.qt, self.output, static=True, compiler=self.compiler)
        depfile = self.directory / "bundle.d"
        resources.write_depfile(depfile, self.output, inputs)
        parsed = DepFile(depfile.read_text(encoding="utf-8").splitlines(keepends=True))
        self.assertEqual(
            set(parsed.get_all_dependencies(self.output.name)), {path.as_posix() for path in inputs}
        )

    def test_meson_reconfigures_after_license_changes(self):
        project = self.directory / "meson project"
        project.mkdir()
        driver = project / "generate.py"
        driver.write_text(
            "import sys\n"
            "sys.path.insert(0, sys.argv[1])\n"
            "import embed_windows_resources as resources\n"
            "inputs = resources.generate_bundle(sys.argv[2], sys.argv[4], "
            "static=True, compiler=sys.argv[3])\n"
            "resources.write_depfile(sys.argv[5], sys.argv[4], inputs)\n",
            encoding="utf-8",
        )
        arguments = ", ".join(
            "'" + path.as_posix().replace("'", "\\'") + "'"
            for path in [driver, ROOT / "scripts", self.qt, self.compiler]
        )
        (project / "meson.build").write_text(
            "project('resource-dependencies')\n"
            "python = import('python').find_installation()\n"
            f"configure_file(output: 'bundle.qrc', command: [python, {arguments}, "
            "'@OUTPUT@', '@DEPFILE@'], depfile: 'bundle.d')\n",
            encoding="utf-8",
        )
        environment = os.environ.copy()
        environment["PATH"] = str(Path(sys.executable).parent) + os.pathsep + environment["PATH"]
        build = project / "build"
        for operation in [["setup", str(build), str(project)], ["compile", "-C", str(build)]]:
            if operation[0] == "compile":
                (self.qt / "LICENSES/Qt-license.txt").write_text("updated Qt license fixture")
            result = subprocess.run(
                [sys.executable, "-m", "mesonbuild.mesonmain", *operation],
                env=environment,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=60,
                check=False,
            )
            self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("updated Qt license fixture", (build / "bundle.txt").read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
