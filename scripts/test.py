"""Run Meson/Qt tests and expose the Qt report even for Windows GUI executables."""

import os
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path


def main():
    for stream in [sys.stdout, sys.stderr]:
        stream.reconfigure(encoding="utf-8", errors="replace")
    build = Path(sys.argv[1] if len(sys.argv) > 1 else "build").resolve()
    environment = os.environ.copy()
    environment["QT_QPA_PLATFORM"] = "offscreen"
    environment["QT_FORCE_STDERR_LOGGING"] = "1"
    if os.name == "nt":
        environment["QT_QPA_FONTDIR"] = str(Path(os.environ["WINDIR"]) / "Fonts")
    result = subprocess.run(["meson", "test", "-C", str(build), "--print-errorlogs"], env=environment)
    report = build / "tests/cpp/native-tests.txt"
    if report.exists():
        lines = report.read_text(encoding="utf-8", errors="replace").splitlines()
        print(
            "\n".join(lines if result.returncode else [line for line in lines if line.startswith("Totals:")])
        )
    try:
        suite = ET.parse(build / "tests/cpp/native-tests.xml").getroot()
        if suite.tag != "testsuite" or not suite.findall("testcase"):
            raise ValueError("Qt Test report contains no test cases")
        if suite.findall(".//failure") or suite.findall(".//error"):
            raise ValueError("Qt Test report contains failed test cases")
    except (OSError, ET.ParseError, ValueError) as error:
        print(f"Invalid or failing JUnit report: {error}", file=sys.stderr)
        return result.returncode or 1
    return result.returncode


if __name__ == "__main__":
    sys.exit(main())
