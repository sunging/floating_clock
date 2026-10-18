"""Expose Qt's complete static dependency and resource lists to Meson."""

import argparse
import json
import re
from pathlib import Path

MODULES = {"Core", "Gui", "Widgets", "Network", "Test"}
PLUGINS = [
    "plugins/platforms/qwindows.prl",
    "plugins/platforms/qoffscreen.prl",
    "plugins/styles/qmodernwindowsstyle.prl",
]


def link_arguments(prefix, modules):
    prefix = Path(prefix).resolve()
    receipt = json.loads((prefix / "static-qt-build.json").read_text())
    if receipt.get("qt") != "6.12.0" or receipt.get("static_compiler_runtime") is not True:
        raise ValueError("Expected the locked static Qt SDK and compiler runtime")
    if not set(modules) <= MODULES:
        raise ValueError("Unsupported static Qt module")
    variables = {
        "QT_INSTALL_PREFIX": prefix,
        "QT_INSTALL_LIBS": prefix / "lib",
        "QT_INSTALL_PLUGINS": prefix / "plugins",
    }
    objects, libraries = [], []
    for relative in [*(f"lib/Qt6{module}.prl" for module in modules), *PLUGINS]:
        path = prefix / relative
        fields = dict(re.findall(r"^(QMAKE_PRL_\w+)\s*=\s*(.*)$", path.read_text(), re.MULTILINE))
        if fields.get("QMAKE_PRL_CONFIG") != "static" or fields.get("QMAKE_PRL_VERSION") != "6.12.0":
            raise ValueError(f"Expected static Qt 6.12.0 metadata: {path}")
        entries = [str(path.parent / fields["QMAKE_PRL_TARGET"])]
        entries += fields["QMAKE_PRL_LIBS_FOR_CMAKE"].split(";")
        for entry in entries:
            entry = entry.strip()
            if not entry:
                continue
            for key, value in variables.items():
                entry = entry.replace(f"$$[{key}]", value.as_posix())
            if re.fullmatch(r"-l[A-Za-z0-9_+.-]+", entry):
                libraries.append(entry)
                continue
            library = Path(entry).resolve()
            if (
                "$$" in entry
                or not library.is_relative_to(prefix)
                or not library.is_file()
                or library.suffix not in {".a", ".obj"}
            ):
                raise ValueError(f"Invalid or missing static Qt link input: {entry}")
            (objects if library.suffix == ".obj" else libraries).append(library.as_posix())
    # Resource constructors are separate objects. Keep each once and resolve library cycles as a group.
    return [*dict.fromkeys(objects), "-Wl,--start-group", *dict.fromkeys(libraries), "-Wl,--end-group"]


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("prefix", type=Path)
    parser.add_argument("modules", nargs="+")
    arguments = parser.parse_args()
    print("\n".join(link_arguments(arguments.prefix, arguments.modules)))
