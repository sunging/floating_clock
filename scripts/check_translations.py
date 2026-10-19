"""Check application catalog coverage, placeholders and completed translations."""

import json
import re
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CATALOG = ROOT / "resources/translations/floating-clock_zh_CN.ts"
LITERAL = r'"(?:\\.|[^"\\])*"'
SOURCE = re.compile(
    r'(?:\bI18n::tr\s*\(|\bQT_TRANSLATE_NOOP\s*\(\s*"FloatingClock"\s*,\s*)'
    r"\s*((?:" + LITERAL + r"\s*)+)"
)


def collect_sources(root=ROOT):
    result = set()
    for path in (root / "src").rglob("*"):
        if path.suffix not in {".cpp", ".h", ".mm"}:
            continue
        for match in SOURCE.finditer(path.read_text(encoding="utf-8")):
            result.add("".join(json.loads(value) for value in re.findall(LITERAL, match[1])))
    return result


def validate_catalog(path=CATALOG, expected=None):
    root = ET.parse(path).getroot()
    errors = []
    if root.attrib.get("language") != "zh_CN" or root.attrib.get("sourcelanguage") != "en":
        errors.append("Expected an English-source Simplified Chinese catalog")
    seen = set()
    for context in root.findall("context"):
        if context.findtext("name") != "FloatingClock":
            errors.append("Unexpected translation context")
        for message in context.findall("message"):
            source = message.findtext("source", "")
            translation = message.find("translation")
            if not source or source in seen:
                errors.append("Empty or duplicate source: " + source)
            seen.add(source)
            if translation is None or translation.attrib.get("type") in {
                "unfinished",
                "obsolete",
                "vanished",
            }:
                errors.append("Incomplete translation: " + source)
                continue
            forms = (
                translation.findall("numerusform")
                if message.attrib.get("numerus") == "yes"
                else [translation]
            )
            if not forms:
                errors.append("Missing plural form: " + source)
            placeholders = Counter(re.findall(r"%L?\d+|%n", source))
            for form in forms:
                text = "".join(form.itertext())
                if not text.strip() or Counter(re.findall(r"%L?\d+|%n", text)) != placeholders:
                    errors.append("Empty translation or mismatched placeholders: " + source)
    if expected is not None:
        errors.extend("Missing translation: " + source for source in sorted(expected - seen))
        errors.extend("Unused translation: " + source for source in sorted(seen - expected))
    return errors


def main():
    expected = collect_sources()
    errors = validate_catalog(expected=expected)
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print(f"Validated {len(expected)} English-source application messages and Chinese translations")
    return bool(errors)


if __name__ == "__main__":
    sys.exit(main())
