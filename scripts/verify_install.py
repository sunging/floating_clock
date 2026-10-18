"""Exercise Debian installation, same-version upgrade and uninstall on disposable CI runners."""

import argparse
import os
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "version.txt").read_text().strip()


def run(*arguments, **kwargs):
    subprocess.run(list(map(str, arguments)), check=True, timeout=120, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=["linux"])
    parser.parse_args()
    if os.environ.get("CI") != "true":
        raise RuntimeError("Installer tests are restricted to disposable CI runners")
    with tempfile.TemporaryDirectory(prefix="clock-install-") as temporary:
        work = Path(temporary)
        config = Path.home() / ".config/floating_clock/config/config.ini"
        package = ROOT / f"dist/floating-clock-{VERSION}-linux-x64.deb"
        arguments = ["sudo", "dpkg", "-i", package]
        executable = Path("/usr/bin/floating-clock")
        if config.exists():
            raise RuntimeError("Refusing to overwrite pre-existing user configuration")
        config.parent.mkdir(parents=True, exist_ok=True)
        sentinel = b"[General]\nfont_size=73\nalarm_timeout_seconds=42\n"
        config.write_bytes(sentinel)
        try:
            for _ in range(2):
                run(*arguments)
                if not executable.is_file():
                    raise RuntimeError("Installed executable is missing")
                environment = os.environ.copy()
                environment["QT_QPA_PLATFORM"] = "xcb"
                for key in ["QT_PLUGIN_PATH", "QT_QPA_PLATFORM_PLUGIN_PATH", "LD_LIBRARY_PATH"]:
                    environment.pop(key, None)
                environment["PATH"] = "/usr/bin:/bin:/usr/sbin:/sbin"
                run(executable, "--smoke-test", "--config", work / "smoke/config.ini", env=environment)
                if config.read_bytes() != sentinel:
                    raise RuntimeError("Installation or upgrade modified user configuration")
        finally:
            if executable.exists():
                run("sudo", "dpkg", "-r", "floating-clock")
        if config.read_bytes() != sentinel:
            raise RuntimeError("Uninstall removed or modified user configuration")
        config.unlink()


if __name__ == "__main__":
    main()
