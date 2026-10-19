"""Generate the Windows translation and license resource bundle for a single executable."""

import argparse
import json
import shutil
import xml.etree.ElementTree as ET
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def generate_bundle(qt, output, *, static=False, compiler=None):
    qt, output = Path(qt).resolve(), Path(output).resolve()
    translation = qt / "translations/qtbase_zh_CN.qm"
    if not translation.is_file() or not translation.stat().st_size:
        raise ValueError("The Qt Chinese translation is missing")
    inputs = {
        "FloatingClock-AGPL-3.0.txt": ROOT / "LICENSE",
        "THIRD_PARTY_NOTICES.md": ROOT / "THIRD_PARTY_NOTICES.md",
        "Qt-translation-source.txt": ROOT / "resources/translations/README.txt",
    }
    directories = [("texts", ROOT / "resources/licenses")]
    if static:
        receipt = qt / "static-qt-build.json"
        data = json.loads(receipt.read_text())
        if data.get("qt") != "6.12.0" or data.get("static_compiler_runtime") is not True:
            raise ValueError("Expected the locked static Qt SDK and runtime")
        inputs["static-qt-build.json"] = receipt
        directories += [("Qt-LICENSES", qt / "LICENSES"), ("Qt-notices", qt / "source-notices")]
        compiler = compiler or shutil.which("g++")
        if not compiler:
            raise ValueError("The MinGW compiler is required for runtime license notices")
        runtime = Path(compiler).resolve().parents[1] / "licenses"
        directories += [(f"MinGW/{name}", runtime / name) for name in ["gcc", "mingw-w64", "winpthreads"]]
    for label, directory in directories:
        files = sorted(path for path in directory.rglob("*") if path.is_file() and path.suffix != ".ts")
        if not files:
            raise ValueError(f"License notices are missing: {directory}")
        inputs.update({f"{label}/{path.relative_to(directory).as_posix()}": path for path in files})
    output.parent.mkdir(parents=True, exist_ok=True)
    notices = output.with_suffix(".txt")
    sections = [
        "Floating Clock: licenses and third-party notices\nSource and build instructions: https://github.com/sunging/floating_clock\n"
    ]
    for label, source in sorted(inputs.items()):
        sections.append(
            f"\n{'=' * 72}\n{label}\n{'=' * 72}\n\n" + source.read_text(encoding="utf-8", errors="replace")
        )
    notices.write_text("\n".join(sections), encoding="utf-8", newline="\n")
    resource = ET.Element("RCC")
    prefix = ET.SubElement(resource, "qresource", prefix="/")
    ET.SubElement(prefix, "file", alias="translations/qtbase_zh_CN.qm").text = translation.as_posix()
    ET.SubElement(prefix, "file", alias="licenses/notices.txt").text = notices.as_posix()
    ET.ElementTree(resource).write(output, encoding="utf-8", xml_declaration=True)
    return [*inputs.values(), translation, ROOT / "packaging/toolchain.json"]


def write_depfile(path, output, dependencies):
    def escape(value):
        return (
            str(value)
            .replace("\\", "/")
            .replace("$", "$$")
            .replace("#", "\\#")
            .replace(" ", "\\ ")
            .replace(":", "\\:")
        )

    Path(path).write_text(
        # Meson's configure_file resolves depfile targets by the output basename.
        f"{escape(Path(output).name)}: {' '.join(escape(item) for item in dependencies)}\n",
        encoding="utf-8",
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--qt", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--depfile", type=Path, required=True)
    parser.add_argument("--static", action="store_true")
    arguments = parser.parse_args()
    dependencies = generate_bundle(arguments.qt, arguments.output, static=arguments.static)
    write_depfile(arguments.depfile, arguments.output, dependencies)
