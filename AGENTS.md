# AGENTS.md

Floating Clock is a C++17 / Qt 6.12 Widgets desktop application built with Meson and Ninja.
Python 3.12+ is build tooling only; there is no Python application runtime.

## Rules

- Support English and Simplified Chinese UI text, with English source strings and Qt catalogs.
  Keep documentation, comments and docstrings in English. Translate built-in UI text, never user data.
  Language previews must preserve draft edits, timer state and independent reminder deadlines.
- Use English Conventional Commits. Do not commit, push, tag or publish unless requested.
- Keep verification records, build logs and local reports in ignored .cache/ storage, never in Git.
  Documentation and code must use portable examples without personal paths, local usernames,
  hostnames, private network addresses or details identifying the developer's machine.
- Preserve user configuration and running applications. Tests must inject temporary configuration,
  fake time, fake sound and fake platform services. Never test against real autostart or alarm settings.
- All settings belong to ConfigStore; add scalars to its shared field table and roundtrip test.
  Runtime timer state is a separate atomic JSON file, not part of a settings dialog draft.
- Keep native platform calls in src/platform with explicit capabilities. Unknown display power is not
  screen-off. Wayland limitations must remain visible to users.
- Windows releases use the locked static Qt SDK and static compiler runtime. Import required plugins
  explicitly and embed translations, notices and the build receipt. Ship only a standalone EXE,
  with corresponding Qt Base source. Do not add Windows ZIP bundles or installers.
- Always recompute effective click-through through ApplicationController::applyClickThrough().
  Move mode, reminders and preview are transient overrides, not persisted preferences.
- Timeouts are finite (1–3600 seconds), fixed per occurrence and independent across reminders.
  New reminders never extend old deadlines. Running timers use suspend-inclusive monotonic time;
  only wall-clock deadlines cross process restarts.
- Preserve stable alarm IDs and consumption while either settings or an alarm editor is open.
- Never remove the user's existing config/, .venv, build SDKs or old installation during a migration.

## Commands

Put the pinned Qt and compiler bin directories on PATH, then:

```text
python -m pip install -r scripts/requirements-build.txt
meson setup build --buildtype=release
meson compile -C build
python scripts/test.py build
python scripts/check_format.py
python scripts/check_translations.py
python -m ruff check scripts tests/tooling
python -m unittest discover -s tests/tooling -v
```

For Windows release builds, first run `python scripts/build_static_qt.py`, put its SDK bin directory
on PATH, set CMAKE_PREFIX_PATH to that SDK, and configure Meson with `-Dstatic_qt=true`.
Keep the shared SDK bin directory on PATH for lrelease as well as the static SDK's bin directory.
The shared Qt development build remains available. Never overwrite the existing SDK to change linkage.

Use python scripts/check_format.py --fix for C++ formatting; ruff format scripts tests/tooling for
build scripts. Builds use warnings as errors. Qt Test and Meson's smoke test use offscreen Qt.
Smoke mode requires --config <isolated-file> and disables real system integration.
Windows sandboxes must allow named pipes for the single-instance test; never skip it to hide a failure.

## Architecture

- src/core: config migration, alarm matching, reminder deadlines, injectable clocks, countdown/stopwatch
  state, language selection and per-config-directory IPC.
- src/ui: clock/reminder window, transactional settings and alarm editor, timer/control panel.
  Translation bindings update widgets in place and must never rebuild or overwrite user-edited values.
- src/platform: Windows power/registry/sound, Linux DPMS/logind/XDG, macOS AppKit/LaunchAgent support.
- src/app.cpp: orchestration, transient state, preview cleanup, persistence and restore debounce.
- tests/cpp: Qt regressions. tests/tooling: artifact publication gate tests.
- scripts and packaging: pinned SDK setup, deployment, signatures and fail-closed release publication.

## Release

version.txt is the single version source. Meson generates executable metadata from it.
Release Please updates versions and CHANGELOG through a PR; merging it builds a draft and publishes
only after five binaries, metadata, checksums and source all match the release commit.
CI directly calls the shared build workflow and explicitly dispatches version-PR checks; do not
rely on GITHUB_TOKEN-generated tags starting workflows. Published releases are immutable.

Pin Actions by full commit SHA and deployment tools by digest. Update locks deliberately, never
silently accept changed continuous downloads. Signing credentials stay outside artifact staging;
never print secrets or commands containing them.

Debian upgrade/uninstall tests are restricted to disposable CI runners. Windows packaging must test
the single EXE in an otherwise empty directory without SDK paths or runtime resource sidecars.
Document cross-platform and physical-device validation gaps honestly: offscreen tests cannot verify
real display power, sound output, screen recording permissions or compositor behavior.
