"""Build the locked Windows Qt Base SDK with static plugins and compiler runtime."""

import argparse
import json
import os
import shutil
import subprocess
import tarfile
from pathlib import Path

from fetch_tool import fetch, sha256

ROOT = Path(__file__).resolve().parents[1]
FEATURES = [
    "opengl",
    "opengl_dynamic",
    "dynamicgl",
    "vulkan",
    "dbus",
    "sql",
    "printsupport",
    "xml",
    "concurrent",
    "ssl",
]


def run(*arguments, **kwargs):
    print("+", " ".join(map(str, arguments)), flush=True)
    return subprocess.run(list(map(str, arguments)), check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--jobs", type=int, default=4)
    parser.add_argument("--base-qt", type=Path)
    arguments = parser.parse_args()
    if os.name != "nt":
        raise RuntimeError("This static SDK configuration is for Windows MinGW only")
    lock = json.loads((ROOT / "packaging/toolchain.json").read_text())
    version = lock["qt"]
    prefix = ROOT / ".tools/qt-static" / version / "mingw_64"
    build = ROOT / ".cache/qt-static/build"
    archive = ROOT / ".cache" / f"qtbase-everywhere-src-{version}.tar.xz"
    source = ROOT / ".cache/qt-static/source" / f"qtbase-everywhere-src-{version}"
    base_qt = arguments.base_qt or ROOT / ".tools/qt" / version / "mingw_64"
    translation_source = ROOT / "resources/translations/qtbase_zh_CN.ts"
    if sha256(translation_source) != lock["qtbase_zh_cn_source"]["sha256"]:
        raise RuntimeError("Qt Chinese translation source differs from the lock")
    receipt = {
        "qt": version,
        "qtbase_source": lock["qtbase_source"],
        "qt_translation_source": lock["qtbase_zh_cn_source"],
        "compiler": lock["mingw"],
        "static_compiler_runtime": True,
        "precompiled_headers": False,
        "disabled_features": FEATURES,
        "opengl_mode": "no",
        "cmake": "3.31.6",
    }
    receipt_path = prefix / "static-qt-build.json"
    # A cached SDK must still provide the exact corresponding source for release artifacts.
    fetch("qtbase_source", archive)
    if receipt_path.is_file():
        if json.loads(receipt_path.read_text()) != receipt:
            raise RuntimeError("Static Qt cache differs from the lock; use a fresh SDK cache")
        if (prefix / "lib/libQt6Widgets.a").is_file() and (prefix / "bin/qmake.exe").is_file():
            print("Using verified static Qt SDK:", prefix)
            return
    source_receipt = source / ".floating-clock-source-sha256"
    if not source_receipt.is_file() or source_receipt.read_text().strip() != lock["qtbase_source"]["sha256"]:
        source.parent.mkdir(parents=True, exist_ok=True)
        with tarfile.open(archive) as payload:
            payload.extractall(source.parent, filter="data")
        source_receipt.write_text(lock["qtbase_source"]["sha256"] + "\n")
    cmake_version = subprocess.check_output(["cmake", "--version"], text=True).splitlines()[0]
    if cmake_version != "cmake version 3.31.6":
        raise RuntimeError("Install the locked CMake 3.31.6 from requirements-build.txt")
    compiler = subprocess.check_output(["g++", "-dumpfullversion"], text=True).strip()
    if compiler != lock["mingw"]:
        raise RuntimeError("Static Qt must use the locked MinGW compiler")
    configure = [
        "cmake",
        "-S",
        source,
        "-B",
        build,
        "-G",
        "Ninja",
        f"-DCMAKE_INSTALL_PREFIX={prefix}",
        "-DCMAKE_BUILD_TYPE=MinSizeRel",
        "-DCMAKE_C_COMPILER=gcc",
        "-DCMAKE_CXX_COMPILER=g++",
        "-DCMAKE_DISABLE_PRECOMPILE_HEADERS=ON",
        "-DBUILD_SHARED_LIBS=OFF",
        "-DFEATURE_static_runtime=ON",
        "-DQT_BUILD_TESTS=OFF",
        "-DQT_BUILD_EXAMPLES=OFF",
        "-DQT_GENERATE_SBOM=OFF",
        "-DINPUT_opengl=no",
    ]
    configure += [f"-DFEATURE_{feature}=OFF" for feature in FEATURES]
    run(*configure)
    run("cmake", "--build", build, "--parallel", max(1, arguments.jobs))
    run("cmake", "--install", build)
    # Meson's Qt tooling probes qmake6 before qmake. Keep both on the static SDK path.
    if not (prefix / "bin/qmake6.exe").exists():
        shutil.copy2(prefix / "bin/qmake.exe", prefix / "bin/qmake6.exe")
    translations = prefix / "translations"
    translations.mkdir(exist_ok=True)
    run(base_qt / "bin/lrelease.exe", translation_source, "-qm", translations / "qtbase_zh_CN.qm")
    shutil.copytree(source / "LICENSES", prefix / "LICENSES", dirs_exist_ok=True)
    notices = prefix / "source-notices"
    notices.mkdir(parents=True, exist_ok=True)
    shutil.copy2(translation_source, notices)
    for path in (source / "src/3rdparty").rglob("*"):
        if path.is_file() and (
            path.name.lower().startswith(("license", "copying", "copyright", "notice"))
            or path.name == "qt_attribution.json"
        ):
            target = notices / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(path, target)
    receipt_path.write_text(json.dumps(receipt, indent=2) + "\n")


if __name__ == "__main__":
    main()
