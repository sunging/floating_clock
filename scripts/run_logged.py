"""Keep native build/deployment output in both the Actions console and report artifacts."""

import os
import subprocess
import sys
from pathlib import Path


def main():
    if len(sys.argv) < 3:
        raise SystemExit("Usage: run_logged.py LOG COMMAND [ARGUMENT ...]")
    destination = Path(sys.argv[1])
    destination.parent.mkdir(parents=True, exist_ok=True)
    command = sys.argv[2:]
    if command[0] == "python":
        command[0] = sys.executable
    environment = os.environ.copy()
    environment["PYTHONIOENCODING"] = "utf-8"
    with destination.open("wb") as log:
        with subprocess.Popen(
            command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, env=environment
        ) as process:
            for line in process.stdout:
                log.write(line)
                log.flush()
                sys.stdout.buffer.write(line)
                sys.stdout.buffer.flush()
            return process.wait()


if __name__ == "__main__":
    sys.exit(main())
