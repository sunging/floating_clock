"""Prepare the pinned native SDK and publish paths to the GitHub runner environment."""

import json
import os
import platform
import subprocess
import sys
from pathlib import Path

from fetch_tool import fetch

ROOT = Path(__file__).resolve().parents[1]


def export(name, value):
    if os.environ.get("GITHUB_ENV"):
        with open(os.environ["GITHUB_ENV"], "a", encoding="utf-8") as stream:
            stream.write(f"{name}={value}\n")
    print(f"{name}={value}")


def add_path(path):
    os.environ["PATH"] = str(path) + os.pathsep + os.environ["PATH"]
    if os.environ.get("GITHUB_PATH"):
        with open(os.environ["GITHUB_PATH"], "a", encoding="utf-8") as stream:
            stream.write(str(path) + "\n")


def main():
    lock = json.loads((ROOT / "packaging/toolchain.json").read_text())
    host = {"Windows": "windows", "Linux": "linux", "Darwin": "mac"}[platform.system()]
    architecture = {"windows": "win64_mingw", "linux": "linux_gcc_64", "mac": "clang_64"}[host]
    directory = {"windows": "mingw_64", "linux": "gcc_64", "mac": "macos"}[host]
    qt = ROOT / ".tools/qt" / lock["qt"] / directory
    if not (qt / "bin" / ("qmake.exe" if host == "windows" else "qmake")).is_file():
        arguments = [
            sys.executable,
            ROOT / "scripts/install_qt.py",
            "install-qt",
            host,
            "desktop",
            lock["qt"],
            architecture,
            "--outputdir",
            ROOT / ".tools/qt",
        ]
        if host != "windows":
            arguments += ["--modules", "qtmultimedia"]
        subprocess.run(arguments, check=True)
    add_path(qt / "bin")
    export("QT_ROOT_DIR", qt)
    export("CMAKE_PREFIX_PATH", qt)
    if host == "windows":
        compiler = ROOT / ".tools/mingw64"
        if not (compiler / "bin/g++.exe").is_file():
            archive = ROOT / ".cache/mingw.7z"
            fetch("mingw_ucrt", archive)
            subprocess.run(["7z", "x", "-y", f"-o{ROOT / '.tools'}", archive], check=True)
        add_path(compiler / "bin")
        export("CXX", "g++")
        subprocess.run([sys.executable, ROOT / "scripts/build_static_qt.py"], check=True)
        qt = ROOT / ".tools/qt-static" / lock["qt"] / "mingw_64"
        add_path(qt / "bin")
        export("QT_ROOT_DIR", qt)
        export("CMAKE_PREFIX_PATH", qt)
    elif host == "linux":
        export("CXX", "g++-13")
    else:
        export("CXX", "clang++")
        export("MACOSX_DEPLOYMENT_TARGET", "14.4")


if __name__ == "__main__":
    main()
