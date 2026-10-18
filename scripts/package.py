"""Build deployable artifacts from one Meson Release build, then smoke-test the payload."""

import argparse
import json
import os
import platform
import plistlib
import re
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path

from fetch_tool import fetch, sha256

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "version.txt").read_text().strip()


def run(*args, **kwargs):
    print("+", " ".join(map(str, args)), flush=True)
    return subprocess.run(list(map(str, args)), check=True, **kwargs)


def licenses(destination, qt):
    target = destination / "licenses"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / "LICENSE", target / "FloatingClock-AGPL-3.0.txt")
    shutil.copy2(ROOT / "THIRD_PARTY_NOTICES.md", target)
    for candidate in [qt / "licenses", qt / "LICENSES", qt.parent.parent / "Licenses"]:
        if candidate.is_dir():
            shutil.copytree(candidate, target / candidate.name, dirs_exist_ok=True)
    for attribution in qt.rglob("*attribution*.json"):
        copy = target / "sdk" / attribution.relative_to(qt)
        copy.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(attribution, copy)
    if (qt / "sbom").is_dir():
        # Binary SPDX JSON retains licensing data without duplicate formats and source inventories.
        sbom_target = target / "qt-sbom"
        sbom_target.mkdir(parents=True, exist_ok=True)
        notices = []
        for sbom in sorted((qt / "sbom").glob("*.spdx.json")):
            shutil.copy2(sbom, sbom_target)
            data = json.loads(sbom.read_text(encoding="utf-8"))
            for package in data.get("packages", []):
                notices.append(
                    "\n".join(
                        str(package.get(key, ""))
                        for key in ["name", "licenseDeclared", "copyrightText", "downloadLocation"]
                    )
                )
            for license_info in data.get("hasExtractedLicensingInfos", []):
                notices.append(license_info["licenseId"] + "\n" + license_info["extractedText"])
        (target / "Qt-attributions.txt").write_text("\n\n".join(notices), encoding="utf-8")
    # SDKs do not consistently include these texts, so also ship reviewed copies.
    local = ROOT / "resources/licenses"
    if local.is_dir():
        shutil.copytree(local, target / "texts", dirs_exist_ok=True)
    if (qt / "source-notices").is_dir():
        shutil.copytree(qt / "source-notices", target / "qt-source-notices", dirs_exist_ok=True)
    if (qt / "static-qt-build.json").is_file():
        shutil.copy2(qt / "static-qt-build.json", target)


def translations(destination, qt):
    target = destination / "translations"
    target.mkdir(parents=True, exist_ok=True)
    shutil.copy2(qt / "translations/qtbase_zh_CN.qm", target)


def smoke(executable, work, platform_name, *launcher_arguments, linkage="shared"):
    config = work / "smoke" / "config.ini"
    environment = os.environ.copy()
    for key in [
        "QT_PLUGIN_PATH",
        "QT_QPA_PLATFORM_PLUGIN_PATH",
        "QML2_IMPORT_PATH",
        "LD_LIBRARY_PATH",
        "DYLD_LIBRARY_PATH",
    ]:
        environment.pop(key, None)
    environment["QT_QPA_PLATFORM"] = {"windows": "windows", "linux": "xcb", "macos": "cocoa"}[platform_name]
    environment["PATH"] = (
        os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "System32")
        if platform_name == "windows"
        else "/usr/bin:/bin:/usr/sbin:/sbin"
    )
    run(
        executable,
        *launcher_arguments,
        "--smoke-test",
        "--config",
        config,
        env=environment,
        cwd=executable.parent,
        timeout=60,
    )
    if not config.exists() or not config.with_name("state.json").exists():
        raise RuntimeError("Packaged application did not persist isolated smoke-test state")
    result = json.loads(config.with_name("smoke-result.json").read_text())
    expected_platform = {"windows": "windows", "linux": "xcb", "macos": "cocoa"}[platform_name]
    expected = {
        "version": VERSION,
        "qt_version": "6.12.0",
        "qt_linkage": linkage,
        "platform": expected_platform,
        "chinese_qt_translation": True,
    }
    if platform_name == "windows":
        expected.update(embedded_translation=True, embedded_licenses=True)
    if result != expected:
        raise RuntimeError("Packaged runtime version or platform plugin does not match the release")


def windows(build, output, qt, work):
    from signing import sign_windows

    stage = work / "windows"
    stage.mkdir()
    executable = stage / "floating-clock.exe"
    shutil.copy2(build / "src/floating-clock.exe", executable)
    if not (qt / "static-qt-build.json").is_file():
        raise RuntimeError("Windows releases require -Dstatic_qt=true and the locked static Qt SDK")
    strip = shutil.which("strip")
    if not strip:
        raise RuntimeError("The MinGW strip tool is required for release packaging")
    run(strip, "--strip-unneeded", executable)
    imports = subprocess.check_output(["objdump", "-p", executable], text=True, errors="replace")
    runtime_dlls = re.findall(r"DLL Name:\s+(\S+)", imports)
    system = Path(os.environ["WINDIR"]) / "System32"
    for name in runtime_dlls:
        lower = name.lower()
        if lower.startswith(("qt6", "libgcc", "libstdc++", "libwinpthread", "libssp")) or (
            not lower.startswith(("api-ms-", "ext-ms-")) and not (system / name).is_file()
        ):
            raise RuntimeError(f"Static Windows executable imports a non-system DLL: {name}")
    sign_windows(executable, work)
    smoke(executable, work, "windows", linkage="static")
    standalone = output / f"floating-clock-{VERSION}-windows-x64.exe"
    shutil.copy2(executable, standalone)
    archive = output / f"floating-clock-{VERSION}-windows-x64.zip"
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED, compresslevel=9) as payload:
        payload.write(standalone, executable.name)
    extracted = work / "单文件 启动验证"
    with zipfile.ZipFile(archive) as payload:
        if payload.testzip() is not None or payload.namelist() != [executable.name]:
            raise RuntimeError("Windows ZIP must contain only the standalone executable")
        payload.extractall(extracted)
    relocated = extracted / "浮动 时钟.exe"
    (extracted / executable.name).rename(relocated)
    smoke(relocated, work / "single-exe-test", "windows", linkage="static")
    if list(extracted.iterdir()) != [relocated]:
        raise RuntimeError("The Windows executable created unexpected runtime sidecar files")
    print("Windows standalone executable bytes:", standalone.stat().st_size)
    return [standalone, archive]


def linux(build, output, qt, work):
    tools = ROOT / ".tools/deploy"
    tools.mkdir(parents=True, exist_ok=True)
    deploy = tools / "linuxdeploy-x86_64.AppImage"
    plugin = tools / "linuxdeploy-plugin-qt-x86_64.AppImage"
    fetch("linuxdeploy", deploy)
    fetch("linuxdeploy_qt", plugin)
    appdir = work / "AppDir"
    appimage = output / f"floating-clock-{VERSION}-linux-x64.AppImage"
    environment = os.environ.copy()
    environment.update(
        {
            "APPIMAGE_EXTRACT_AND_RUN": "1",
            "QMAKE": str(qt / "bin/qmake"),
            "QML_SOURCES_PATHS": "",
            "EXTRA_QT_MODULES": "multimedia;waylandcompositor",
            "EXTRA_PLATFORM_PLUGINS": ";".join(
                path.name for path in sorted((qt / "plugins/platforms").glob("*wayland*.so"))
            ),
            "OUTPUT": str(appimage),
            "VERSION": VERSION,
            "PATH": str(tools) + os.pathsep + environment["PATH"],
        }
    )
    run(
        deploy,
        "--appdir",
        appdir,
        "--executable",
        build / "src/floating-clock",
        "--desktop-file",
        ROOT / "packaging/floating-clock.desktop",
        "--icon-file",
        ROOT / "resources/clock.png",
        "--icon-filename",
        "floating-clock",
        "--plugin",
        "qt",
        env=environment,
    )
    licenses(appdir / "usr/share/floating-clock", qt)
    translations(appdir / "usr/share/floating-clock", qt)
    smoke(appdir / "usr/bin/floating-clock", work, "linux")
    run(deploy, "--appdir", appdir, "--output", "appimage", env=environment)
    if not appimage.is_file():
        raise RuntimeError("AppImage generation did not produce the expected versioned file")
    # An AppImage launcher needs no FUSE service in CI.
    smoke(appimage, work / "appimage-test", "linux", "--appimage-extract-and-run")

    debroot = work / "deb"
    shutil.copytree(appdir / "usr", debroot / "opt/floating-clock/usr", symlinks=True)
    bindir = debroot / "usr/bin"
    bindir.mkdir(parents=True)
    launcher = bindir / "floating-clock"
    launcher.write_text('#!/bin/sh\nexec /opt/floating-clock/usr/bin/floating-clock "$@"\n')
    launcher.chmod(0o755)
    applications = debroot / "usr/share/applications"
    applications.mkdir(parents=True)
    shutil.copy2(ROOT / "packaging/floating-clock.desktop", applications)
    icons = debroot / "usr/share/icons/hicolor/256x256/apps"
    icons.mkdir(parents=True)
    shutil.copy2(ROOT / "resources/clock.png", icons / "floating-clock.png")
    control = debroot / "DEBIAN"
    control.mkdir()
    (control / "control").write_text(
        f"Package: floating-clock\nVersion: {VERSION}\nArchitecture: amd64\n"
        "Maintainer: sunging <noreply@github.com>\nSection: utils\nPriority: optional\n"
        "Depends: libc6 (>= 2.39), libstdc++6 (>= 13), libgl1, libegl1, libx11-6, libxext6, "
        "libxkbcommon0, libxkbcommon-x11-0, libxcb-cursor0, libasound2t64, libpulse0, "
        "libglib2.0-0t64, libfontconfig1, libdbus-1-3\n"
        "Homepage: https://github.com/sunging/floating_clock\n"
        "Description: Floating clock, alarms, countdown and stopwatch\n"
        " Qt Widgets desktop utility with per-reminder timeouts.\n"
    )
    deb = output / f"floating-clock-{VERSION}-linux-x64.deb"
    run("dpkg-deb", "--root-owner-group", "--build", debroot, deb)
    extracted = work / "deb-extracted"
    run("dpkg-deb", "--extract", deb, extracted)
    smoke(extracted / "opt/floating-clock/usr/bin/floating-clock", work / "deb-test", "linux")
    return [appimage, deb]


def macos(build, output, qt, work):
    from signing import notarize_mac, sign_mac_app

    architecture = "arm64" if platform.machine() == "arm64" else "x64"
    application = work / "Floating Clock.app"
    contents = application / "Contents"
    binary = contents / "MacOS/floating-clock"
    binary.parent.mkdir(parents=True)
    shutil.copy2(build / "src/floating-clock", binary)
    resources = contents / "Resources"
    resources.mkdir()
    iconset = work / "clock.iconset"
    iconset.mkdir()
    for size in [16, 32, 128, 256, 512]:
        for scale in [1, 2]:
            name = f"icon_{size}x{size}" + ("@2x" if scale == 2 else "") + ".png"
            run(
                "sips",
                "-z",
                size * scale,
                size * scale,
                ROOT / "resources/clock.png",
                "--out",
                iconset / name,
                stdout=subprocess.DEVNULL,
            )
    run("iconutil", "-c", "icns", iconset, "-o", resources / "clock.icns")
    with (contents / "Info.plist").open("wb") as stream:
        plistlib.dump(
            {
                "CFBundleName": "Floating Clock",
                "CFBundleDisplayName": "浮动时钟",
                "CFBundleIdentifier": "com.sunging.floating-clock",
                "CFBundleExecutable": "floating-clock",
                "CFBundlePackageType": "APPL",
                "CFBundleShortVersionString": VERSION,
                "CFBundleVersion": VERSION,
                "CFBundleIconFile": "clock.icns",
                "LSMinimumSystemVersion": "14.4",
                "LSUIElement": True,
                "NSHighResolutionCapable": True,
            },
            stream,
        )
    run(qt / "bin/macdeployqt", application, "-always-overwrite")
    licenses(resources, qt)
    translations(resources, qt)
    sign_mac_app(application, work)
    smoke(binary, work, "macos")
    run("codesign", "--verify", "--deep", "--strict", application)
    dmg = output / f"floating-clock-{VERSION}-macos-{architecture}.dmg"
    # Only the application and the Applications shortcut enter the disk image.
    image_root = work / "image"
    image_root.mkdir()
    shutil.copytree(application, image_root / application.name, symlinks=True)
    (image_root / "Applications").symlink_to("/Applications", target_is_directory=True)
    run(
        "hdiutil",
        "create",
        "-volname",
        "Floating Clock",
        "-srcfolder",
        image_root,
        "-ov",
        "-format",
        "UDZO",
        dmg,
    )
    notarize_mac(dmg, work)
    run("hdiutil", "verify", dmg)
    mount = work / "mounted"
    mount.mkdir()
    run("hdiutil", "attach", dmg, "-readonly", "-nobrowse", "-mountpoint", mount)
    try:
        smoke(mount / application.name / "Contents/MacOS/floating-clock", work / "dmg-test", "macos")
    finally:
        run("hdiutil", "detach", mount)
    return [dmg]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=["windows", "linux", "macos"])
    parser.add_argument("--build", type=Path, default=ROOT / "build")
    parser.add_argument("--output", type=Path, default=ROOT / "dist")
    parser.add_argument("--qt", type=Path, required=True)
    arguments = parser.parse_args()
    project = json.loads((arguments.build / "meson-info/intro-projectinfo.json").read_text())
    if project["version"] != VERSION:
        raise RuntimeError("The build is stale; reconfigure and compile before packaging")
    sdk_version = subprocess.check_output(
        [
            str(arguments.qt.resolve() / "bin" / ("qmake.exe" if os.name == "nt" else "qmake")),
            "-query",
            "QT_VERSION",
        ],
        text=True,
    ).strip()
    if sdk_version != "6.12.0":
        raise RuntimeError("Packaging requires the locked Qt 6.12.0 SDK")
    output = arguments.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    cache = ROOT / ".cache"
    cache.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="package-", dir=cache) as directory:
        work = Path(directory).resolve()
        if not work.is_relative_to(cache.resolve()):
            raise RuntimeError("Staging directory escaped the workspace cache")
        artifacts = globals()[arguments.platform](
            arguments.build.resolve(), output, arguments.qt.resolve(), work
        )
    target = (
        arguments.platform
        + "-"
        + ("arm64" if arguments.platform == "macos" and platform.machine() == "arm64" else "x64")
    )
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip()
    dirty = bool(
        subprocess.check_output(
            ["git", "status", "--porcelain", "--untracked-files=normal"], cwd=ROOT, text=True
        ).strip()
    )
    manifest = {
        "version": VERSION,
        "commit": commit,
        "dirty": dirty,
        "platform": target,
        "qt": "6.12.0",
        "qt_linkage": "static" if (arguments.qt / "static-qt-build.json").is_file() else "shared",
        "signing": ("certificate" if os.environ.get("WINDOWS_CERTIFICATE_BASE64") else "unsigned")
        if arguments.platform == "windows"
        else ("developer-id" if os.environ.get("MACOS_CERTIFICATE_BASE64") else "ad-hoc")
        if arguments.platform == "macos"
        else "unsigned",
        "files": {path.name: sha256(path) for path in artifacts},
    }
    if arguments.platform == "windows":
        manifest["windows_distribution"] = "single-exe"
    if manifest["qt_linkage"] == "static":
        lock = json.loads((ROOT / "packaging/toolchain.json").read_text())
        source = output / f"qtbase-{lock['qt']}-source.tar.xz"
        shutil.copy2(ROOT / ".cache" / f"qtbase-everywhere-src-{lock['qt']}.tar.xz", source)
        if sha256(source) != lock["qtbase_source"]["sha256"]:
            raise RuntimeError("Static Qt corresponding source does not match the SDK lock")
        manifest["source_inputs"] = {source.name: sha256(source)}
    (output / f"build-metadata-{target}.json").write_text(json.dumps(manifest, indent=2) + "\n")


if __name__ == "__main__":
    main()
