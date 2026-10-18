"""Validate draft identity and complete artifact sets before publishing a GitHub Release."""

import argparse
import base64
import hashlib
import json
import os
import re
import subprocess
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TAG = re.compile(r"v(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\Z")
COMMIT = re.compile(r"[0-9a-f]{40}\Z")
TARGETS = {
    "windows-x64": [".exe", ".zip"],
    "linux-x64": [".AppImage", ".deb"],
    "macos-x64": [".dmg"],
    "macos-arm64": [".dmg"],
}


def version_from_tag(tag):
    if not TAG.fullmatch(tag):
        raise ValueError("Expected a stable version tag such as v0.2.0")
    return tag[1:]


def digest(path):
    result = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def static_qt_source():
    lock = json.loads((ROOT / "packaging/toolchain.json").read_text())
    return {f"qtbase-{lock['qt']}-source.tar.xz": lock["qtbase_source"]["sha256"]}


def gh(*arguments, payload=None, optional=False):
    command = ["gh", *arguments]
    if payload is not None:
        command.extend(["--input", "-"])
    result = subprocess.run(
        command,
        input=json.dumps(payload) if payload is not None else None,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        if optional and "404" in result.stderr:
            return None
        raise RuntimeError(result.stderr.strip() or "GitHub command failed")
    return json.loads(result.stdout) if result.stdout.strip() else None


def repository():
    repo = os.environ["GITHUB_REPOSITORY"]
    if not re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", repo):
        raise ValueError("Invalid repository identity")
    return repo


def output(**values):
    path = os.environ.get("GITHUB_OUTPUT")
    if path:
        with open(path, "a", encoding="utf-8") as stream:
            for key, value in values.items():
                stream.write(f"{key}={value}\n")


def resolve_tag(repo, tag):
    ref = gh("api", f"repos/{repo}/git/ref/tags/{tag}", optional=True)
    if ref is None:
        return None
    obj = ref["object"]
    for _ in range(8):
        if obj["type"] == "commit":
            return obj["sha"]
        if obj["type"] != "tag":
            break
        obj = gh("api", f"repos/{repo}/git/tags/{obj['sha']}")["object"]
    raise RuntimeError("Tag does not resolve to a commit")


def find_release(repo, tag):
    # The tag endpoint only promises published releases; authenticated lists include drafts.
    matches = []
    page = 1
    while True:
        releases = gh("api", f"repos/{repo}/releases?per_page=100&page={page}")
        matches.extend(release for release in releases if release["tag_name"] == tag)
        if len(releases) < 100:
            break
        page += 1
    if len(matches) != 1:
        raise RuntimeError("Expected exactly one release for the requested tag")
    return matches[0]


def require_draft(release, tag):
    if release.get("tag_name") != tag or release.get("draft") is not True:
        raise RuntimeError("Only the matching draft may be modified; published releases are immutable")


def verify_source(repo, tag, sha):
    version = version_from_tag(tag)
    if not COMMIT.fullmatch(sha):
        raise ValueError("A full commit SHA is required")
    comparison = gh("api", f"repos/{repo}/compare/{sha}...main")
    if comparison["status"] not in {"ahead", "identical"}:
        raise RuntimeError("Release commit is not on main")
    source = gh("api", f"repos/{repo}/contents/version.txt?ref={sha}")
    actual = base64.b64decode(source["content"]).decode().strip()
    if actual != version:
        raise RuntimeError("Tag and source version differ")


def prepare():
    repo = repository()
    for pr in json.loads(os.environ.get("RELEASE_PRS") or "[]"):
        branch = pr["headBranchName"]
        # GITHUB_TOKEN-created PRs need an explicit dispatch to obtain CI checks.
        gh(
            "api",
            f"repos/{repo}/actions/workflows/ci.yml/dispatches",
            "--method",
            "POST",
            payload={"ref": branch},
        )
    retry = os.environ.get("RETRY_TAG", "")
    if not retry and os.environ.get("RELEASE_CREATED") != "true":
        output(ready="false")
        return
    tag = retry or os.environ["RELEASE_TAG"]
    version_from_tag(tag)
    release = find_release(repo, tag)
    require_draft(release, tag)
    sha = resolve_tag(repo, tag)
    expected = os.environ.get("RELEASE_SHA", "") if not retry else ""
    if sha is None:
        # Some release-please versions defer tags for draft releases.
        sha = expected or release["target_commitish"]
        verify_source(repo, tag, sha)
        gh(
            "api",
            f"repos/{repo}/git/refs",
            "--method",
            "POST",
            payload={"ref": f"refs/tags/{tag}", "sha": sha},
        )
    if expected and expected != sha:
        raise RuntimeError("Release output and existing tag point to different commits")
    verify_source(repo, tag, sha)
    output(ready="true", tag=tag, sha=sha)


def validate_artifacts(directory, version, sha):
    if not COMMIT.fullmatch(sha):
        raise ValueError("Invalid commit SHA")
    version_from_tag("v" + version)
    directory = Path(directory).resolve()
    manifests = []
    artifacts = []
    for target, extensions in TARGETS.items():
        manifest_file = directory / f"build-metadata-{target}.json"
        manifest = json.loads(manifest_file.read_text())
        if (
            manifest.get("version") != version
            or manifest.get("commit") != sha
            or manifest.get("platform") != target
            or manifest.get("dirty") is not False
            or manifest.get("qt") != "6.12.0"
        ):
            raise ValueError(f"Build identity mismatch: {target}")
        expected = {f"floating-clock-{version}-{target}{extension}" for extension in extensions}
        if set(manifest.get("files", {})) != expected:
            raise ValueError(f"Incomplete or unexpected artifact set: {target}")
        if target == "windows-x64":
            if manifest.get("qt_linkage") != "static":
                raise ValueError("Windows release must use the static Qt build")
            if manifest.get("windows_distribution") != "single-exe":
                raise ValueError("Windows release must use the standalone executable")
            sources = static_qt_source()
            if manifest.get("source_inputs") != sources:
                raise ValueError("Static Qt corresponding source does not match the lock")
            for name, checksum in sources.items():
                source = directory / name
                if source.is_symlink() or not source.is_file() or digest(source) != checksum:
                    raise ValueError("Static Qt corresponding source is missing or altered")
                artifacts.append(source)
        for name in sorted(expected):
            path = directory / name
            if path.is_symlink() or not path.is_file() or path.stat().st_size == 0:
                raise ValueError(f"Invalid artifact: {name}")
            if digest(path) != manifest["files"][name]:
                raise ValueError(f"Artifact checksum mismatch: {name}")
            if target == "windows-x64" and path.suffix == ".zip":
                with zipfile.ZipFile(path) as payload:
                    if payload.namelist() != ["floating-clock.exe"]:
                        raise ValueError("Windows ZIP must contain only the standalone executable")
                    if payload.testzip() is not None:
                        raise ValueError("Windows ZIP failed its integrity check")
                    contents = payload.read("floating-clock.exe")
                    executable = directory / f"floating-clock-{version}-windows-x64.exe"
                    if hashlib.sha256(contents).hexdigest() != manifest["files"][executable.name]:
                        raise ValueError("Windows ZIP and standalone executable differ")
            artifacts.append(path)
        manifests.append(manifest)
    return artifacts, manifests


def publish():
    repo = repository()
    tag, sha = os.environ["RELEASE_TAG"], os.environ["RELEASE_SHA"]
    version = version_from_tag(tag)
    verify_source(repo, tag, sha)
    if resolve_tag(repo, tag) != sha:
        raise RuntimeError("Release tag moved during the build")
    release = find_release(repo, tag)
    require_draft(release, tag)
    directory = ROOT / "dist"
    artifacts, manifests = validate_artifacts(directory, version, sha)
    source = directory / f"floating-clock-{version}-source.tar.gz"
    subprocess.run(
        [
            "git",
            "archive",
            "--format=tar.gz",
            f"--prefix=floating-clock-{version}/",
            f"--output={source}",
            sha,
        ],
        check=True,
        cwd=ROOT,
    )
    info = directory / "build-info.json"
    info.write_text(json.dumps({"version": version, "commit": sha, "builds": manifests}, indent=2) + "\n")
    artifacts += [source, info]
    checksums = directory / "SHA256SUMS"
    checksums.write_text("".join(f"{digest(path)}  {path.name}\n" for path in sorted(artifacts)))
    # Only a draft is mutable, and only after the entire set has passed verification.
    subprocess.run(
        ["gh", "release", "upload", tag, *map(str, artifacts), str(checksums), "--clobber", "--repo", repo],
        check=True,
    )
    current = gh("api", f"repos/{repo}/releases/{release['id']}")
    require_draft(current, tag)
    expected_names = {path.name for path in artifacts} | {"SHA256SUMS"}
    uploaded = {asset["name"]: asset for asset in current["assets"]}
    if set(uploaded) != expected_names:
        raise RuntimeError("Remote draft has missing or unexpected assets; publication stopped")
    for path in [*artifacts, checksums]:
        asset = uploaded[path.name]
        if asset.get("state") != "uploaded":
            raise RuntimeError("Remote asset upload is not complete")
        if asset["size"] != path.stat().st_size:
            raise RuntimeError("Remote asset size differs from verified local artifact")
        if asset.get("digest") != "sha256:" + digest(path):
            raise RuntimeError("Remote asset digest differs from verified local artifact")
    if resolve_tag(repo, tag) != sha:
        raise RuntimeError("Release tag moved during the upload")
    gh(
        "api",
        f"repos/{repo}/releases/{release['id']}",
        "--method",
        "PATCH",
        payload={"draft": False, "make_latest": "true"},
    )
    confirmed = gh("api", f"repos/{repo}/releases/{release['id']}")
    if confirmed["draft"] or confirmed["tag_name"] != tag:
        raise RuntimeError("Publication could not be confirmed")
    print("Published:", confirmed["html_url"])


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["prepare", "publish"])
    args = parser.parse_args()
    globals()[args.command]()
