# Floating Clock

A floating desktop clock built with **C++17, Qt 6.12 Widgets, Meson and Ninja**, for Windows,
Linux and macOS. The application has no Python runtime dependency. Python 3.12+ is used only
for building, testing and packaging.

## Features

- A frameless, transparent, always-on-top clock, with a tray menu and a control panel when no tray is available.
- Adjustable font, color, opacity, seconds and date, automatic background color adaptation, and reversible settings previews.
- Click-through mode, temporary move mode, and position restoration across display layout, scale and wake changes.
- Multiple alarms with one-shot, daily, weekday and custom weekday rules. Concurrent reminders share one popup.
- Independent reminder timeouts: **60 seconds** by default, configurable from **1 to 3600 seconds**, with optional per-alarm overrides. New reminders never extend existing deadlines.
- Configurable reminder text, background, opacity, flashing, scale and layout. Long content scrolls while the stop button remains visible.
- Silent mode, system/built-in sounds and custom WAV files. Visual reminders remain available when sound fails.
- One countdown and one stopwatch with laps. Changing the floating display does not stop background timers.
- User-level autostart, one instance per configuration directory, and optional reminders while the screen is off.
- **English and Simplified Chinese**, with automatic system-language selection and live language previews.

## Installation and use

Download a package from [GitHub Releases](https://github.com/sunging/floating_clock/releases)
and verify it against that release's `SHA256SUMS`.

| Platform | Minimum release environment | Package |
| --- | --- | --- |
| Windows x64 | Windows 10 1809 / Windows 11 | Standalone EXE |
| Linux x64 | Ubuntu 24.04+ or a compatible glibc 2.39 desktop | AppImage, DEB |
| macOS Intel | macOS 14.4+ | x64 DMG |
| macOS Apple Silicon | macOS 14.4+ | arm64 DMG |

On Windows, run the downloaded EXE directly. Qt, platform/style plugins, the C++ runtime,
application translations, the Qt Chinese catalog, icons, sounds and license notices are embedded.
No DLLs or installer are required. To update, exit the application and replace the EXE in place;
settings are retained. Disable autostart before removing the EXE. Removing it does not delete settings.

On Linux, make the AppImage executable. Without FUSE, use `--appimage-extract-and-run`.
Install the DEB with `sudo apt install ./floating-clock-*.deb`. On macOS, drag the application
from the DMG into Applications.

Windows builds are unsigned by default; macOS uses ad-hoc signing unless release credentials
are configured. If macOS blocks the first launch, use the application's Open Anyway entry in
System Settings, Privacy & Security. Signing status is recorded in `build-info.json`.

- **Control panel:** use the tray menu or right-click an interactive clock. Without a tray, closing the panel exits the application.
- **Move:** select Move clock in the tray or control panel, then drag the clock. The original click-through preference is restored afterward.
- **Adaptive color:** enable Adapt text color to the background under Settings, Appearance. It is off by default. Sampling runs immediately after enabling, previewing or moving, and every two seconds afterward.
- **Stop reminders:** click the popup, its stop button or the tray command. Each reminder also stops automatically at its own deadline.
- **Timers:** the control panel has separate countdown and stopwatch tabs. Select the floating display independently at the top.
- **Language:** choose Follow system, English or Simplified Chinese under Settings, General, Language. Changes preview immediately; OK saves the preference and Cancel restores the previous language. Follow system uses the first supported OS UI language, falling back to English. Chinese locales use the Simplified Chinese catalog.
- **General settings:** configure click-through, start at login and screen-off reminders under Settings, General. Platform capability notices also appear here.
- **Quit:** use the tray or control-panel command. With a tray available, closing the panel only hides it.
- **About and licenses:** inspect the version and notices from the control panel. Windows embeds the complete notices for offline reading, copying and export.

Language changes update built-in labels, menus, dialogs and generated reminder text without
restarting timers or extending reminder deadlines. Alarm names, content, file paths and other
user-entered data are never translated.

## Timing behavior

Running countdowns, stopwatches and reminder deadlines use suspend-inclusive monotonic time.
Wall-clock corrections do not change their progress. Scheduled alarms use local wall time,
do not replay missed minutes, and fire at most once per alarm in a matching minute.

- Countdown and stopwatch support start, pause, resume and reset. Running state is saved every five seconds and on exit.
- A countdown resumes after restart using its saved wall-clock deadline. An already expired countdown stays finished without ringing.
- The stopwatch restores elapsed time and laps, paused. An abnormal exit can lose progress since the last checkpoint.
- A countdown that finishes during sleep, or while the screen is off and such reminders are disabled, stays finished after recovery without ringing.
- Each reminder fixes its timeout and sound settings when triggered. Merged reminders keep independent deadlines and sound eligibility. Wake recovery removes expired reminders, including silent ones.
- Reminder and sound previews last at most three seconds and are cleared when settings close. They do not consume real alarms.

## Configuration and migration

Legacy QSettings INI files, alarm JSON, stable alarm IDs and the old `repeat_daily` field remain
supported. New fields include `schema_version`, `language`, global `alarm_timeout_seconds` and
optional per-alarm `timeout_seconds`. Missing fields use defaults. Invalid scalar values fall back,
duplicate IDs are repaired, and invalid alarm entries are skipped with a warning.

| Mode | Default settings location |
| --- | --- |
| `portable.flag` beside the executable | `config/config.ini` beside the executable |
| Windows standalone or development build | `%APPDATA%\FloatingClock\config\config.ini` |
| Linux | `$XDG_CONFIG_HOME/floating_clock/config/config.ini`, normally `~/.config/floating_clock/config/config.ini` |
| macOS | `~/Library/Application Support/FloatingClock/config/config.ini` |

`state.json` beside the INI stores timer state independently of settings drafts. Instances using
the same configuration directory share the timer state. `--config <file>` selects an explicit
configuration, independently of the working directory. Windows uses the user configuration
directory by default and still supports `portable.flag` and explicit portable paths.

Exit the old Python application before importing its INI from the control panel. Import and the
first save of an older schema create a `.bak` before overwriting; a failed backup cancels the write.
Save errors appear in the panel and tray. Older applications refuse to overwrite settings or timer
state from a newer schema. Importing settings leaves runtime timer progress intact and applies
autostart to the current executable. Import a former source checkout's `config/` file manually.

## Platform behavior

Windows uses Win32 click-through and power notifications, WinMM audio, and the current user's
Run registry entry. It needs neither Qt Multimedia nor FFmpeg. Custom WAV and built-in/system
sounds support looping and finite timeout cleanup.

macOS uses AppKit click-through and sleep notifications, and a user LaunchAgent for the next login.
Automatic background sampling requires screen recording permission. Linux X11 uses desktop
window hints, DPMS and logind. Autostart uses XDG; AppImage autostart points to the outer image.

Wayland controls absolute positioning and stacking, and limits persistent background sampling
and power detection. Settings show these limitations; dragging is delegated to the compositor.
Core timers, sound and reminders remain usable. Unknown display power is treated as on.

## Building and testing

Use Python 3.12+, **Qt 6.12.0**, Meson/Ninja and a C++17 compiler. Windows uses MinGW-w64 15.1 UCRT,
Linux uses GCC 13, and macOS uses Apple Clang. Build tool versions are pinned in
`scripts/requirements-build.txt`; deployment tools and hashes are locked in `packaging/toolchain.json`.

This Windows example assumes the matching compiler is installed under `.tools/mingw64`:

```powershell
python -m venv .tools/build-env
.\.tools\build-env\Scripts\Activate.ps1
python -m pip install -r scripts/requirements-build.txt
python scripts/install_qt.py install-qt windows desktop 6.12.0 win64_mingw --outputdir .tools/qt
$env:PATH = "$PWD\.tools\qt\6.12.0\mingw_64\bin;$PWD\.tools\mingw64\bin;" + $env:PATH
$env:CXX = "g++"
python scripts/build_static_qt.py --jobs 4
$env:PATH = "$PWD\.tools\qt-static\6.12.0\mingw_64\bin;" + $env:PATH
$env:CMAKE_PREFIX_PATH = "$PWD\.tools\qt-static\6.12.0\mingw_64"
meson setup build-static --buildtype=release -Dstatic_qt=true
meson compile -C build-static
python scripts/test.py build-static
.\build-static\src\floating-clock.exe --control
```

`scripts/install_qt.py` handles Qt 6.12's Windows archive layout. `scripts/ci_environment.py` can
install the complete locked toolchain. Keep the shared SDK's `bin` on PATH for `lrelease` when
using the static SDK. The application itself does not load that SDK at runtime.

On Linux/macOS, add Qt's `bin` to PATH, configure with
`meson setup build --buildtype=release -Dstatic_qt=false`, then compile and run `python scripts/test.py build`.
The CI workflow lists Linux system dependencies. Qt's Linux download architecture is `linux_gcc_64`;
its extracted SDK directory is `gcc_64`.

The first static Qt build compiles the locked Qt Base source. Subsequent builds reuse the verified
`.tools/qt-static` SDK. Source, build options and compiler identity are recorded in
`static-qt-build.json`; a receipt mismatch stops reuse. Keep a separate shared development SDK.
Windows release packaging requires `-Dstatic_qt=true`.

```text
python scripts/check_format.py
python scripts/check_translations.py
python -m ruff check scripts tests/tooling
python -m unittest discover -s tests/tooling -v
python scripts/test.py build-static
python scripts/package.py windows --build build-static --qt .tools/qt-static/6.12.0/mingw_64
```

Meson's Qt module compiles the application TS catalog and embeds the QM resource on every platform.
English is the source language; add Chinese translations to
`resources/translations/floating-clock_zh_CN.ts`. Mark fixed labels with
`QT_TRANSLATE_NOOP("FloatingClock", "English source")`, bind them through `src/ui/translation.h`,
and use `fc::I18n::tr()` for generated text. Catalog checks reject missing, unfinished and malformed
placeholder translations. Qt Linguist's optional `lupdate` also requires its QML runtime; ordinary
builds only need `lrelease`. See `resources/translations/README.txt` for catalog maintenance.

Windows also has native desktop tests for transparent hit testing, dragging and background color:

```powershell
$env:QT_QPA_PLATFORM = "windows"
.\build-static\tests\cpp\windows-ui-tests.exe
$env:QT_SCALE_FACTOR = "1.5"
.\build-static\tests\cpp\windows-ui-tests.exe
Remove-Item Env:QT_SCALE_FACTOR
Remove-Item Env:QT_QPA_PLATFORM
```

Tests use isolated configuration, injectable time and fake sound/platform services. Smoke mode
requires an explicit isolated `--config` and disables real autostart, sound and visible windows.
Single-instance tests require local named pipes. Packaging checks both UI languages, including
the relocated Windows EXE in an otherwise empty directory with SDK paths removed.

Keep verification records and local reports in ignored `.cache/` storage. Documentation and code
must use portable examples without developer-machine paths, usernames, hostnames or private addresses.

## CI and releases

Pull requests and pushes to `main`/`develop` run four native builds, Qt Test, formatting, translation
checks, packaging and package startup tests. Windows caches its locked static SDK and Qt Base source;
the first build allows up to 120 minutes. Linux uses disposable runners for DEB install, upgrade
and uninstall tests, and runs ASan/UBSan. Leak checking excludes global allocations in prebuilt Qt.
Physical multi-monitor behavior, display power, audio output and macOS permissions need separate
platform acceptance testing; offscreen checks cannot verify them.

Release Please maintains a version PR from English Conventional Commits and updates `version.txt`
and the changelog. After a human merges that PR, the workflow creates a matching tag and draft,
builds the exact commit and verifies all five binaries plus the corresponding Qt Base source.
Only then does it upload application source, `build-info.json`, `SHA256SUMS` and publish the release.
Windows accepts one standalone EXE, with no extra ZIP or installer. Missing/unexpected remote assets,
source mismatches and checksum failures stop publication. Failures retain a draft that can be retried
through the Release workflow with the original tag. Published releases are not overwritten.

The workflow explicitly dispatches CI for bot-created version PRs and calls the shared build workflow,
without relying on `GITHUB_TOKEN` tag events. Enable Actions-created PRs in repository settings.
Publication needs `contents: write` and `pull-requests: write`; dispatching CI needs `actions: write`.
Regular CI has read-only permissions. Signing credentials are used only for release builds.

| Optional signing | Secrets |
| --- | --- |
| Windows PFX | `WINDOWS_CERTIFICATE_BASE64`, `WINDOWS_CERTIFICATE_PASSWORD` |
| macOS Developer ID | `MACOS_CERTIFICATE_BASE64`, `MACOS_CERTIFICATE_PASSWORD`, `MACOS_SIGN_IDENTITY` |
| macOS notarization API | `MACOS_NOTARY_KEY_BASE64`, `MACOS_NOTARY_KEY_ID`, `MACOS_NOTARY_ISSUER` |

Without credentials, Windows remains unsigned and macOS uses ad-hoc signing. Developer ID signing
also requires notarization; any signing or notarization failure stops publication.
