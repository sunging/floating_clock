# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

See [AGENTS.md](AGENTS.md) for commands, architecture, and conventions. Key points:

- **Commits:** use Conventional Commits with English messages.
- **No test suite:** verify via headless smoke tests (`QT_QPA_PLATFORM=offscreen`).
- **Windows-first:** click-through, sounds, and autostart are guarded by `sys.platform`; keep non-Windows degradation graceful.
