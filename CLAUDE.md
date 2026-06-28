# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See [AGENTS.md](AGENTS.md) for commands, architecture, and conventions. Key points:

- **Commits:** use Conventional Commits with English messages.
- **Tests:** pytest suite under `tests/`; run headless with `QT_QPA_PLATFORM=offscreen uv run pytest`. CI runs it on Windows (see `.github/workflows/tests.yml`). For things hard to unit-test, fall back to a headless smoke test.
- **Windows-first:** click-through, sounds, and autostart are guarded by `sys.platform`; keep non-Windows degradation graceful.
