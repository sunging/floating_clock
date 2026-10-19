# Changelog

## [0.2.0](https://github.com/sunging/floating_clock/compare/v0.1.0...v0.2.0) (2026-10-19)


### Features

* add bilingual UI and reorganize general settings ([72661a8](https://github.com/sunging/floating_clock/commit/72661a8fe22e866b8f856b8ee9f751c7abb77232))
* migrate floating clock to C++ with timers and reminder timeouts ([6c5b21a](https://github.com/sunging/floating_clock/commit/6c5b21a819e5ab824a52ae352b0fda593e869610))

## Changelog

## Unreleased

### Features

- Rewrite the application in C++17 with Qt 6.12 Widgets and Meson, without a Python runtime dependency.
- Support English and Simplified Chinese, automatic system-language selection, persisted preferences and reversible live language previews.
- Preserve transparent always-on-top display, click-through and move modes, adaptive colors, multi-display restoration, appearance previews, repeating alarms, custom WAV sounds, autostart and screen-off suppression.
- Stop reminders after 60 seconds by default, with global and per-alarm timeouts from 1 to 3600 seconds and independent deadlines for merged reminders.
- Add a countdown and stopwatch with laps, pause/resume and restart recovery, independent of floating display selection.
- Use a standalone static-Qt Windows EXE with no bundled DLLs, extra ZIP or installer.
- Provide Linux AppImage/DEB and Intel/Apple Silicon macOS DMG packages, with four-target CI and artifact integrity gates.
- Preserve legacy settings and stable alarm IDs, import older configuration, save runtime state atomically, and isolate single instances by configuration directory.

### Fixes and improvements

- Restore dragging with click-through disabled or move mode enabled, and refresh adaptive colors immediately after changes or movement.
- Keep reminder text and stop controls compact while preserving scrolling for long content.
- Preserve settings rollback, one-shot consumption during editing, concurrent reminders, wake recovery and multi-display drag position synchronization.
- Keep timer progress, alarm names/content, unsaved edits and reminder deadlines intact during language changes.
- Group language, click-through, start at login and screen-off reminders under General settings.
- Use English documentation, source messages, comments and docstrings; keep verification records outside Git.
- Check native Windows interaction and 150% scaling, Linux ASan/UBSan, package startup in both languages, and DEB configuration preservation across upgrades and removal.

### Release notes

- Minimum release environments are Windows 10/11 x64, Ubuntu 24.04-compatible desktops, and macOS 14.4+.
- Windows is unsigned by default; macOS uses ad-hoc signing. Real display power, sound, multi-monitor and permission interaction need separate platform acceptance testing.
- Include checksums, build information, application source and the corresponding Qt Base source for the statically linked Windows build.
