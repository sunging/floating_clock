"""Check or format only this project's C++ sources, never SDK or build directories."""

import argparse
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fix", action="store_true")
    arguments = parser.parse_args()
    sources = sorted(
        path
        for folder in [ROOT / "src", ROOT / "tests/cpp"]
        for path in folder.rglob("*")
        if path.suffix in {".h", ".cpp", ".mm"}
    )
    flags = ["-i"] if arguments.fix else ["--dry-run", "--Werror"]
    subprocess.run(["clang-format", *flags, *map(str, sources)], check=True, cwd=ROOT)


if __name__ == "__main__":
    main()
