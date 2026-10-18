"""Publication must reject mixed commits, incomplete packages and tampered bytes."""

import importlib.util
import json
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location("release", ROOT / "scripts/release.py")
release = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(release)


class ArtifactFixture(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.directory = self.root / "dist"
        self.directory.mkdir()
        self.sha = "a" * 40
        source = self.directory / "qtbase-6.12.0-source.tar.xz"
        source.write_bytes(b"isolated static Qt source fixture")
        self.source = source
        self.source_lock = {source.name: release.digest(source)}
        source_patch = patch.object(release, "static_qt_source", return_value=self.source_lock)
        source_patch.start()
        self.addCleanup(source_patch.stop)
        for target, extensions in release.TARGETS.items():
            files = {}
            for extension in extensions:
                path = self.directory / f"floating-clock-0.2.0-{target}{extension}"
                if extension == ".zip":
                    with zipfile.ZipFile(path, "w") as payload:
                        payload.writestr("floating-clock.exe", (target + ".exe").encode())
                else:
                    path.write_bytes((target + extension).encode())
                files[path.name] = release.digest(path)
            manifest = {
                "version": "0.2.0",
                "commit": self.sha,
                "dirty": False,
                "platform": target,
                "qt": "6.12.0",
                "files": files,
            }
            if target == "windows-x64":
                manifest.update(
                    qt_linkage="static", windows_distribution="single-exe", source_inputs=self.source_lock
                )
            (self.directory / f"build-metadata-{target}.json").write_text(json.dumps(manifest))


class ReleaseTests(ArtifactFixture):
    def test_complete_set(self):
        files, manifests = release.validate_artifacts(self.directory, "0.2.0", self.sha)
        self.assertEqual(len(files), 7)
        self.assertEqual(len(manifests), 4)

    def test_tags_are_data_not_shell_expressions(self):
        for invalid in ["main", "../v0.2.0", "v1.2.3;echo x", "v01.2.3", "v1.2.3\n", "v1.2"]:
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                release.version_from_tag(invalid)
        self.assertEqual(release.version_from_tag("v0.2.0"), "0.2.0")

    def test_missing_platform(self):
        (self.directory / "build-metadata-macos-arm64.json").unlink()
        with self.assertRaises(FileNotFoundError):
            release.validate_artifacts(self.directory, "0.2.0", self.sha)

    def test_altered_payload(self):
        (self.directory / "floating-clock-0.2.0-windows-x64.zip").write_bytes(b"different")
        with self.assertRaisesRegex(ValueError, "checksum"):
            release.validate_artifacts(self.directory, "0.2.0", self.sha)

    def test_wrong_version_commit_dirty_or_platform(self):
        path = self.directory / "build-metadata-linux-x64.json"
        original = json.loads(path.read_text())
        for key, value in [
            ("commit", "b" * 40),
            ("version", "0.3.0"),
            ("dirty", True),
            ("platform", "linux-arm64"),
            ("qt", "6.8.3"),
        ]:
            with self.subTest(key=key):
                path.write_text(json.dumps({**original, key: value}))
                with self.assertRaisesRegex(ValueError, "identity"):
                    release.validate_artifacts(self.directory, "0.2.0", self.sha)

    def test_unexpected_file_not_published(self):
        path = self.directory / "build-metadata-linux-x64.json"
        data = json.loads(path.read_text())
        data["files"]["../../secret"] = "bad"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "artifact set"):
            release.validate_artifacts(self.directory, "0.2.0", self.sha)

    def test_dynamic_windows_build_rejected(self):
        path = self.directory / "build-metadata-windows-x64.json"
        data = json.loads(path.read_text())
        data["qt_linkage"] = "shared"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "static Qt"):
            release.validate_artifacts(self.directory, "0.2.0", self.sha)

    def test_static_qt_source_required(self):
        self.source.write_bytes(b"altered source")
        with self.assertRaisesRegex(ValueError, "source"):
            release.validate_artifacts(self.directory, "0.2.0", self.sha)

    def test_windows_zip_must_contain_only_the_executable(self):
        archive = self.directory / "floating-clock-0.2.0-windows-x64.zip"
        with zipfile.ZipFile(archive, "a") as payload:
            payload.writestr("platforms/qwindows.dll", b"unexpected dynamic plugin")
        path = self.directory / "build-metadata-windows-x64.json"
        data = json.loads(path.read_text())
        data["files"][archive.name] = release.digest(archive)
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "only the standalone"):
            release.validate_artifacts(self.directory, "0.2.0", self.sha)

    def test_windows_zip_must_match_standalone_executable(self):
        archive = self.directory / "floating-clock-0.2.0-windows-x64.zip"
        with zipfile.ZipFile(archive, "w") as payload:
            payload.writestr("floating-clock.exe", b"different executable")
        path = self.directory / "build-metadata-windows-x64.json"
        data = json.loads(path.read_text())
        data["files"][archive.name] = release.digest(archive)
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "executable differ"):
            release.validate_artifacts(self.directory, "0.2.0", self.sha)

    def test_windows_installer_distribution_rejected(self):
        path = self.directory / "build-metadata-windows-x64.json"
        data = json.loads(path.read_text())
        data["windows_distribution"] = "installer"
        path.write_text(json.dumps(data))
        with self.assertRaisesRegex(ValueError, "standalone"):
            release.validate_artifacts(self.directory, "0.2.0", self.sha)


class ReleaseFlowTests(ArtifactFixture):
    def setUp(self):
        super().setUp()
        self.tag = "v0.2.0"
        self.draft = {"id": 42, "tag_name": self.tag, "draft": True, "target_commitish": self.sha}
        self.uploaded = False
        self.published = False
        self.change_remote = lambda assets: None
        for mocking in [
            patch.object(release, "ROOT", self.root),
            patch.dict(
                release.os.environ,
                {
                    "GITHUB_REPOSITORY": "owner/clock",
                    "RELEASE_TAG": self.tag,
                    "RELEASE_SHA": self.sha,
                    "RELEASE_CREATED": "true",
                },
                clear=True,
            ),
        ]:
            mocking.start()
            self.addCleanup(mocking.stop)
        for name, mocking in {
            "gh": patch.object(release, "gh", side_effect=self.github),
            "verify": patch.object(release, "verify_source"),
            "resolve": patch.object(release, "resolve_tag", return_value=self.sha),
            "run": patch.object(release.subprocess, "run", side_effect=self.command),
            "output": patch.object(release, "output"),
        }.items():
            setattr(self, name, mocking.start())
            self.addCleanup(mocking.stop)

    def assets(self):
        paths, _ = release.validate_artifacts(self.directory, "0.2.0", self.sha)
        paths += [
            self.directory / "floating-clock-0.2.0-source.tar.gz",
            self.directory / "build-info.json",
            self.directory / "SHA256SUMS",
        ]
        assets = [
            {
                "name": path.name,
                "size": path.stat().st_size,
                "state": "uploaded",
                "digest": "sha256:" + release.digest(path),
            }
            for path in paths
        ]
        self.change_remote(assets)
        return assets

    def github(self, *arguments, payload=None, **_):
        endpoint = arguments[1]
        if endpoint.endswith("releases?per_page=100&page=1"):
            return [self.draft.copy()]
        if endpoint.endswith("releases/42"):
            if "PATCH" in arguments:
                self.assertTrue(self.uploaded)
                self.assertEqual(payload, {"draft": False, "make_latest": "true"})
                self.published = True
            return {
                **self.draft,
                "draft": not self.published,
                "assets": self.assets(),
                "html_url": "https://example.invalid/release",
            }
        if endpoint.endswith("ci.yml/dispatches"):
            self.assertEqual(payload, {"ref": "release-please--branches--main"})
            return None
        if endpoint.endswith("git/refs"):
            self.assertEqual(payload, {"ref": "refs/tags/v0.2.0", "sha": self.sha})
            return None
        self.fail(f"Unexpected GitHub request: {arguments}")

    def command(self, command, **_):
        if command[:2] == ["git", "archive"]:
            self.assertEqual(command[-1], self.sha)
            (self.directory / "floating-clock-0.2.0-source.tar.gz").write_bytes(b"verified source")
        elif command[:3] == ["gh", "release", "upload"]:
            self.assertEqual(command[3], self.tag)
            self.assertIn("--clobber", command)
            self.uploaded = True
        else:
            self.fail(f"Unexpected subprocess: {command}")

    def test_draft_lookup_paginates_and_rejects_ambiguity(self):
        page = [{"tag_name": "older"}] * 100
        with patch.object(release, "gh", side_effect=[page, [self.draft]]) as api:
            self.assertEqual(release.find_release("owner/clock", self.tag), self.draft)
            self.assertTrue(api.call_args.args[1].endswith("page=2"))
        for entries in [[], [self.draft, self.draft]]:
            with patch.object(release, "gh", return_value=entries), self.assertRaises(RuntimeError):
                release.find_release("owner/clock", self.tag)

    def test_prepare_dispatches_version_pr_and_checks_tag(self):
        release.os.environ["RELEASE_PRS"] = json.dumps([{"headBranchName": "release-please--branches--main"}])
        release.prepare()
        self.assertTrue(any("dispatches" in call.args[1] for call in self.gh.call_args_list))
        self.verify.assert_called_once_with("owner/clock", self.tag, self.sha)
        self.output.assert_called_once_with(ready="true", tag=self.tag, sha=self.sha)

    def test_prepare_can_create_missing_draft_tag_and_retry(self):
        self.resolve.return_value = None
        release.os.environ["RETRY_TAG"] = self.tag
        release.os.environ["RELEASE_SHA"] = ""
        release.prepare()
        self.assertTrue(any(call.args[1].endswith("git/refs") for call in self.gh.call_args_list))
        self.output.assert_called_once_with(ready="true", tag=self.tag, sha=self.sha)

    def test_prepare_without_release_only_dispatches_ci(self):
        release.os.environ["RELEASE_CREATED"] = "false"
        release.prepare()
        self.gh.assert_not_called()
        self.output.assert_called_once_with(ready="false")

    def test_prepare_rejects_published_or_moved_tag(self):
        self.draft["draft"] = False
        with self.assertRaisesRegex(RuntimeError, "immutable"):
            release.prepare()
        self.draft["draft"] = True
        self.resolve.return_value = "b" * 40
        with self.assertRaisesRegex(RuntimeError, "different commits"):
            release.prepare()
        self.run.assert_not_called()

    def test_publish_checks_remote_set_before_visibility(self):
        release.publish()
        self.assertTrue(self.published)
        self.assertEqual(self.resolve.call_count, 2)
        info = json.loads((self.directory / "build-info.json").read_text())
        self.assertEqual(info["commit"], self.sha)
        self.assertEqual(len(info["builds"]), 4)
        self.assertEqual(len((self.directory / "SHA256SUMS").read_text().splitlines()), 9)

    def test_publish_keeps_draft_for_bad_remote_assets(self):
        changes = {
            "missing": lambda assets: assets.pop(),
            "extra": lambda assets: assets.append({"name": "unexpected"}),
            "size": lambda assets: assets[0].update(size=0),
            "digest": lambda assets: assets[0].update(digest="sha256:wrong"),
            "absent digest": lambda assets: assets[0].pop("digest"),
            "incomplete": lambda assets: assets[0].update(state="starter"),
        }
        for name, change in changes.items():
            with self.subTest(name=name):
                self.change_remote = change
                with self.assertRaises(RuntimeError):
                    release.publish()
                self.assertFalse(self.published)

    def test_publish_rechecks_tag_after_upload(self):
        self.resolve.side_effect = [self.sha, "b" * 40]
        with self.assertRaisesRegex(RuntimeError, "moved during the upload"):
            release.publish()
        self.assertTrue(self.uploaded)
        self.assertFalse(self.published)

    def test_publish_rechecks_draft_after_upload(self):
        def changed_release(*arguments, **kwargs):
            result = self.github(*arguments, **kwargs)
            if arguments[1].endswith("releases/42"):
                result["draft"] = False
            return result

        with (
            patch.object(release, "gh", side_effect=changed_release),
            self.assertRaisesRegex(RuntimeError, "immutable"),
        ):
            release.publish()
        self.assertTrue(self.uploaded)
        self.assertFalse(self.published)

    def test_publish_rejects_published_release_before_upload(self):
        self.draft["draft"] = False
        with self.assertRaisesRegex(RuntimeError, "immutable"):
            release.publish()
        self.assertFalse(self.uploaded)
        self.run.assert_not_called()


if __name__ == "__main__":
    unittest.main()
