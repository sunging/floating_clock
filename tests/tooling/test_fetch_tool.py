"""Tool download failures must preserve existing tools and close temporary files on Windows."""

import hashlib
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("fetch_tool", ROOT / "scripts/fetch_tool.py")
fetch_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(fetch_tool)


class FetchToolTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        (self.root / "packaging").mkdir()
        self.payload = b"locked tool bytes"
        (self.root / "packaging/toolchain.json").write_text(
            json.dumps(
                {
                    "test": {
                        "url": "https://example.invalid/tool",
                        "sha256": hashlib.sha256(self.payload).hexdigest(),
                    }
                }
            )
        )
        self.destination = self.root / "tools/tool.bin"
        self.destination.parent.mkdir()
        root_patch = patch.object(fetch_tool, "ROOT", self.root)
        root_patch.start()
        self.addCleanup(root_patch.stop)

    def test_verified_cache_skips_network(self):
        self.destination.write_bytes(self.payload)
        with patch.object(fetch_tool.requests, "get") as request:
            fetch_tool.fetch("test", self.destination)
        request.assert_not_called()

    def test_failed_download_closes_and_removes_temporary_file(self):
        with (
            patch.object(fetch_tool.requests, "get", side_effect=fetch_tool.requests.Timeout),
            self.assertRaises(fetch_tool.requests.Timeout),
        ):
            fetch_tool.fetch("test", self.destination)
        self.assertEqual(list(self.destination.parent.iterdir()), [])

    def test_digest_mismatch_preserves_existing_tool(self):
        self.destination.write_bytes(b"previous tool")
        response = MagicMock(status_code=200)
        response.iter_content.return_value = [b"untrusted replacement"]
        with (
            patch.object(fetch_tool.requests, "get", return_value=response),
            self.assertRaisesRegex(RuntimeError, "Digest mismatch"),
        ):
            fetch_tool.fetch("test", self.destination)
        self.assertEqual(self.destination.read_bytes(), b"previous tool")
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])

    def test_download_commits_only_verified_bytes(self):
        response = MagicMock(status_code=200)
        response.iter_content.return_value = [self.payload[:5], self.payload[5:]]
        with patch.object(fetch_tool.requests, "get", return_value=response):
            fetch_tool.fetch("test", self.destination)
        self.assertEqual(self.destination.read_bytes(), self.payload)
        self.assertEqual(list(self.destination.parent.iterdir()), [self.destination])


if __name__ == "__main__":
    unittest.main()
