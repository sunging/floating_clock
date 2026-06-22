# AGENTS.md

Guidance for AI agents and contributors working in this repository.

## Project

Windows desktop **floating clock**: frameless, always-on-top, translucent,
click-through, with alarms. Built with **Python + [uv](https://docs.astral.sh/uv/) + PySide6 (Qt)**.

## Commands

```powershell
uv sync                          # install deps (first time)
uv run floating-clock            # run (entry point = floating_clock.app:main)
uv run python -m floating_clock  # run via __main__

# Package a single-file exe (output in dist/)
uv run --with pyinstaller pyinstaller --noconsole --onefile `
  --name floating-clock src/floating_clock/__main__.py
```

There is no test suite. Verify changes with a **headless smoke test** so no
window pops up — set the offscreen Qt platform and drive the widgets directly:

```bash
QT_QPA_PLATFORM=offscreen uv run python -c "from PySide6.QtWidgets import QApplication; app=QApplication([]); ..."
```

`Config.save()` writes `config.ini` into the **current working directory**, so
run throwaway scripts from a temp dir or delete the file afterward (it is
gitignored).

## Architecture

The app is a tray-resident Qt application; there is no main window in the
taskbar (`setQuitOnLastWindowClosed(False)` — lifecycle is the tray icon).

- **`app.py` — `FloatingClockApp`** is the orchestrator. It loads `Config`,
  builds the `ClockWindow`, `AlarmManager`, and the tray menu, then runs a
  single **500 ms `QTimer`** whose `_tick` calls `clock.update_time()` and
  `alarm_manager.check()`. All cross-component wiring lives here via callbacks.
- **`config.py` — `Config`** is a dataclass holding every adjustable setting.
  `Config.load()` / `Config.save()` are the *only* persistence API; they use
  `QSettings(IniFormat)` pointed at `config.ini` in the cwd (not the registry).
  Alarms are stored as a JSON string inside the INI.
- **`clock_window.py` — `ClockWindow`** is the frameless/top-most/translucent
  `QWidget` (a centered `QLabel`). `apply_config()` is the single place that
  applies appearance (font/color/opacity/position/click-through). Mouse
  click-through is a **Win32 extended-window-style** hack (`WS_EX_TRANSPARENT`
  via `ctypes`). Dragging is gated behind click-through being off; a real drag
  fires the `on_moved` callback used to auto-exit "move mode".
- **`alarm.py` — `Alarm` / `AlarmManager`** match alarms by `HH:MM` with a
  per-minute dedup key (the 500 ms tick would otherwise fire repeatedly).
  One-shot alarms (`repeat_daily=False`) disable themselves on fire.
- **`autostart.py`** registers/unregisters under the current-user `Run`
  registry key. The launch command differs between a frozen PyInstaller exe
  (`sys.frozen`) and script mode (`pythonw.exe -m floating_clock`).
- **`settings_dialog.py` — `SettingsDialog`** edits a *deepcopy* of `Config`.
  An `on_preview` callback pushes live appearance changes to the clock as the
  user edits; `result_config()` is read only when the dialog is accepted.

### Cross-cutting conventions

- **Platform guards:** click-through, `winsound`, and autostart/registry are
  Windows-only and guarded by `sys.platform == "win32"` / `is_supported()`.
  Non-Windows must still display the clock — degrade silently, never raise.
- **When config is saved:** settings accepted, click-through toggled, drag
  released, and one-shot alarm fired. Keep these in sync when adding state.
- **Comments and docstrings are in Chinese** to match the existing codebase.

## Commits

Use **Conventional Commits** with English messages
(`feat:`, `fix:`, `feat(config):`, `feat(clock):`, etc.).
