"""Fetch a deployment tool only if its digest matches the reviewed toolchain lock."""

import argparse
import hashlib
import json
import os
import tempfile
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def fetch(name, destination):
    tools = json.loads((ROOT / "packaging/toolchain.json").read_text())
    tool = tools[name]
    destination = Path(destination).resolve()
    destination.parent.mkdir(parents=True, exist_ok=True)
    if destination.exists() and sha256(destination) == tool["sha256"]:
        return
    with tempfile.NamedTemporaryFile(dir=destination.parent, delete=False) as stream:
        temporary = Path(stream.name)
        try:
            url = tool["url"]
            for _ in range(8):
                response = requests.get(url, timeout=(20, 120), stream=True, allow_redirects=False)
                if response.status_code in {301, 302, 303, 307, 308}:
                    url = response.headers["Location"]
                    response.close()
                    if not url.startswith("https://"):
                        raise RuntimeError("Refusing a non-HTTPS tool redirect")
                    continue
                response.raise_for_status()
                break
            else:
                raise RuntimeError("Too many tool download redirects")
            with response:
                for block in response.iter_content(1024 * 1024):
                    stream.write(block)
            stream.close()
            if sha256(temporary) != tool["sha256"]:
                raise RuntimeError(f"Digest mismatch for {name}; review the toolchain lock before updating")
            os.replace(temporary, destination)
            destination.chmod(0o755)
        finally:
            stream.close()
            temporary.unlink(missing_ok=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("name", choices=["linuxdeploy", "linuxdeploy_qt", "mingw_ucrt"])
    parser.add_argument("destination", type=Path)
    arguments = parser.parse_args()
    fetch(arguments.name, arguments.destination)
