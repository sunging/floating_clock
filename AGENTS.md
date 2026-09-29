# AGENTS.md

Guidance for AI agents and contributors working in this repository.

## Project

Windows desktop **floating clock**: frameless, always-on-top, translucent,
click-through, with alarms. Built with **Python + [uv](https://docs.astral.sh/uv/) + PySide6 (Qt)**.
Supports Python 3.9+ (CI tests 3.9 and 3.12), so avoid 3.10+ syntax such as
`match` or `X | Y` outside annotations.

## Commands

```powershell
uv sync                          # install deps incl. dev group (pytest, ruff)
uv run floating-clock            # run (entry point = floating_clock.app:main)
uv run python -m floating_clock  # run via __main__

# On Windows the app relaunches itself detached (pythonw) and the command
# returns at once. Run in the foreground to see output / tracebacks:
$env:FLOATING_CLOCK_DETACHED = "1"; uv run floating-clock

uv run ruff check                # lint (config in pyproject.toml)

# Package a single-file exe (output in dist/)
uv run --with pyinstaller pyinstaller --noconsole --onefile `
  --name floating-clock src/floating_clock/__main__.py
```

There is a **pytest** suite under `tests/`. Run it headless so no window pops
up — set the offscreen Qt platform:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"; uv run pytest
```

CI (`.github/workflows/tests.yml`) runs `ruff check` and the tests on
`windows-latest` (Python 3.9 and 3.12) for every push to `main` / `develop`
and every PR. Windows is used so the win32-only tests (`screen.py`,
`winsound`, background relaunch) actually run instead of being skipped. CI
installs with `--frozen`, so commit `uv.lock` whenever dependencies change.

For changes hard to cover with a unit test, also do a **headless smoke test** —
drive the widgets directly with the offscreen platform set:

```bash
QT_QPA_PLATFORM=offscreen uv run python -c "from PySide6.QtWidgets import QApplication; app=QApplication([]); ..."
```

The version lives only in `floating_clock/__init__.py` (`__version__`);
hatch reads it from there (`[tool.hatch.version]`).

### Config file location

`Config.save()` writes `config/config.ini` under `app_dir()`, independent of
the working directory so autostart reads the same file:

- frozen PyInstaller exe → the exe's folder (portable);
- installed under `site-packages` (pip / `uv tool`) → `%APPDATA%\FloatingClock`
  (XDG config dir elsewhere), so reinstalling the tool keeps settings;
- source checkout → the project root (the `config/` folder is gitignored).

Tests never touch the real file: the autouse `temp_config_dir` fixture in
`tests/conftest.py` redirects `app_dir()` / `config_path()` to a temp dir.

## Architecture

The app is a tray-resident Qt application; there is no main window in the
taskbar (`setQuitOnLastWindowClosed(False)` — lifecycle is the tray icon).

- **`app.py` — `FloatingClockApp`** is the orchestrator. It loads `Config`,
  builds the `ClockWindow`, `AlarmManager`, and the tray menu, then runs a
  single **500 ms `QTimer`** whose `_tick` calls `clock.update_time()`,
  `alarm_manager.check()`, and (every 4th tick) `clock.update_auto_color()`.
  All cross-component wiring lives here via callbacks.
  - `_tick` gates `alarm_manager.check()` behind `_alarms_active()` so a dark
    screen suppresses alarms entirely (no fire, no one-shot consumption) unless
    `ring_when_screen_off` is set.
  - **Click-through** is a user preference (`config.click_through`) plus
    transient overrides: `_apply_click_through()` turns it off while in move
    mode or while an alarm rings, without changing the saved preference.
    Always go through `_apply_click_through()` rather than calling
    `clock.set_click_through()` directly.
  - **Position restore:** Windows may shove top-level windows around when
    displays sleep/wake or are re-enumerated. Screen add/remove/geometry
    signals, the window's `screenChanged`, and `ScreenStateMonitor.on_wake`
    all restart a 750 ms single-shot timer that calls
    `clock.restore_position()` (deferred while a drag is in progress).
  - Only one `SettingsDialog` exists at a time; if a one-shot alarm fires while
    it is open, `mark_alarm_fired()` updates the dialog's copy by alarm `id`.
  - `main()` first calls `_detach_to_background()`: on Windows, when not
    frozen and `FLOATING_CLOCK_DETACHED` is unset, it relaunches
    `pythonw -m floating_clock` detached and exits the parent.
- **`config.py` — `Config`** is a dataclass holding every adjustable setting.
  `Config.load()` / `Config.save()` are the *only* persistence API; they use
  `QSettings(IniFormat)` (not the registry). Every scalar field has an entry in
  the **`_READERS` field table** (`(raw, default) -> value`) used by both load
  and save; the INI key is the field name. Alarms are stored as a JSON string
  under `alarms`. Malformed values fall back to defaults instead of raising.
  Also defines the alarm popup layout constants (`POPUP_LAYOUT_*`).
- **`_coerce.py`** holds lenient converters (`to_bool`, `clamp_int`,
  `clamp_float`, `clamp_position`) shared by config and alarm loading.
- **`clock_window.py` — `ClockWindow`** is the frameless/top-most/translucent
  `QWidget`: a centered `QLabel` for the time, plus a hidden alarm panel
  (read-only `QPlainTextEdit` + "停止闹钟" button) shown while ringing.
  `apply_config()` is the single place that applies appearance
  (font/color/opacity/position/click-through). The alarm popup is sized to at
  most 80% of its display, shrinking the font or scrolling rather than
  truncating. Mouse click-through is a **Win32 extended-window-style** hack
  (`WS_EX_TRANSPARENT` via `ctypes`). Dragging only works while click-through
  is off; a real drag saves the position and fires `on_moved` (used to
  auto-exit move mode). Auto-color samples the screen behind the window and
  picks the light/dark text color by median luminance.
- **`alarm.py` — `Alarm` / `AlarmManager`** match alarms by `HH:MM` plus repeat
  rule (`once` / `daily` / `weekdays` / `custom`) with a per-minute dedup key
  (the 500 ms tick would otherwise fire repeatedly). Every alarm due in a
  minute fires in **one** `on_trigger(list[Alarm])` call (one sound, one popup
  titled "N 个闹钟" when several). One-shot alarms disable themselves on fire.
  Each alarm has a stable `id` (uuid hex, excluded from equality); call
  `alarm.normalize()` after mutating repeat fields.
- **`autostart.py`** registers/unregisters under the current-user `Run`
  registry key. The launch command differs between a frozen PyInstaller exe
  (`sys.frozen`) and script mode (`gui_interpreter() -m floating_clock`, where
  `gui_interpreter()` prefers `pythonw.exe` next to `sys.executable`).
- **`sound.py`** plays the alarm tone via `winsound` in three modes — `silent`,
  `system` (an SND_ALIAS from `SYSTEM_SOUNDS`), and `custom` (a WAV via
  SND_FILENAME, falling back to the default alias if the path is missing).
- **`screen.py` — `ScreenStateMonitor`** is a `QAbstractNativeEventFilter` that
  subscribes to `GUID_CONSOLE_DISPLAY_STATE` via
  `RegisterPowerSettingNotification` and parses `WM_POWERBROADCAST` (all via
  `ctypes`) to track whether the monitor is on, calling `on_wake` on
  resume / display-on. Defaults to "on" when unknown.
- **`settings_dialog.py` — `SettingsDialog`** edits a *deepcopy* of `Config`.
  An `on_preview` callback pushes live appearance changes to the clock as the
  user edits; `result_config()` is read only when the dialog is accepted, and
  the app restores the real config either way. Widget→config mapping lives in
  `_apply_appearance_values` / `_apply_alarm_popup_values` /
  `_apply_sound_values`. **`AlarmEditDialog`** edits a single alarm.

### Adding a setting

1. Add the field (with default) to `Config` in `config.py`.
2. Add a reader to `_READERS` (the `test_every_field_is_persisted` guard test
   fails otherwise).
3. Add the widget in `SettingsDialog` and set the field in the matching
   `_apply_*_values` method (appearance ones also show in live preview).
4. Apply it at runtime (usually `ClockWindow.apply_config()`), and extend
   `test_every_field_roundtrips` with a non-default value.

### Cross-cutting conventions

- **Platform guards:** click-through, `winsound`, autostart/registry, the
  power-state monitor, and the background relaunch are Windows-only and
  guarded by `sys.platform == "win32"` / `is_supported()`. Non-Windows must
  still display the clock — degrade silently, never raise (e.g. `screen.py`
  always reports the display as on).
- **When config is saved:** settings accepted, click-through toggled, drag
  released, and one-shot alarm fired. Keep these in sync when adding state.
- **Comments and docstrings are in English.** User-facing strings (tray menu
  labels, dialog text, default alarm names) stay in Chinese — only code comments
  and docstrings are English. README.md is user-facing and in Chinese.

## Commits

Use **Conventional Commits** with English messages
(`feat:`, `fix:`, `feat(config):`, `feat(clock):`, etc.).
