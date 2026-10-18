"""Check pinned SDK requests without downloading SDKs or modifying the host environment."""

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("ci_environment", ROOT / "scripts/ci_environment.py")
ci = importlib.util.module_from_spec(SPEC)
with patch.dict(sys.modules, {"fetch_tool": MagicMock()}):
    SPEC.loader.exec_module(ci)


class EnvironmentTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "packaging").mkdir()
        (self.root / "packaging/toolchain.json").write_text('{"qt":"6.12.0"}')
        for name, mocking in {
            "root_patch": patch.object(ci, "ROOT", self.root),
            "environment": patch.dict(ci.os.environ, {"PATH": "/isolated"}, clear=True),
            "run": patch.object(ci.subprocess, "run"),
            "export": patch.object(ci, "export"),
        }.items():
            setattr(self, name, mocking.start())
            self.addCleanup(mocking.stop)

    def test_linux_sdk_uses_current_repository_architecture(self):
        with patch.object(ci.platform, "system", return_value="Linux"):
            ci.main()
        command = self.run.call_args.args[0]
        self.assertEqual(command[2:7], ["install-qt", "linux", "desktop", "6.12.0", "linux_gcc_64"])
        self.assertEqual(command[-2:], ["--modules", "qtmultimedia"])
        self.export.assert_any_call("QT_ROOT_DIR", self.root / ".tools/qt/6.12.0/gcc_64")
        self.export.assert_any_call("CXX", "g++-13")

    def test_mac_sdk_uses_universal_archive_and_deployment_floor(self):
        with patch.object(ci.platform, "system", return_value="Darwin"):
            ci.main()
        self.assertEqual(self.run.call_args.args[0][6], "clang_64")
        self.export.assert_any_call("QT_ROOT_DIR", self.root / ".tools/qt/6.12.0/macos")
        self.export.assert_any_call("MACOSX_DEPLOYMENT_TARGET", "14.4")

    def test_existing_linux_sdk_is_reused(self):
        qmake = self.root / ".tools/qt/6.12.0/gcc_64/bin/qmake"
        qmake.parent.mkdir(parents=True)
        qmake.touch()
        with patch.object(ci.platform, "system", return_value="Linux"):
            ci.main()
        self.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
