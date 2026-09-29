"""Tests for the interpreter/command helpers in autostart.py and app's background relaunch."""

import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

from floating_clock import app as app_module
from floating_clock import autostart


def test_gui_interpreter_prefers_pythonw(tmp_path, monkeypatch):
    python = tmp_path / "python.exe"
    pythonw = tmp_path / "pythonw.exe"
    python.touch()
    monkeypatch.setattr(sys, "executable", str(python))
    assert autostart.gui_interpreter() == python
    pythonw.touch()
    assert autostart.gui_interpreter() == pythonw


def test_launch_command_script_mode(tmp_path, monkeypatch):
    python = tmp_path / "python.exe"
    (tmp_path / "pythonw.exe").touch()
    monkeypatch.setattr(sys, "executable", str(python))
    monkeypatch.delattr(sys, "frozen", raising=False)
    assert autostart._launch_command() == f'"{tmp_path / "pythonw.exe"}" -m floating_clock'


def test_launch_command_frozen(monkeypatch):
    exe = Path("C:/apps/floating-clock.exe")
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    assert autostart._launch_command() == f'"{exe}"'


@pytest.mark.skipif(sys.platform != "win32", reason="background relaunch is Windows-only")
def test_detach_relaunches_with_sentinel(monkeypatch):
    popen = Mock()
    monkeypatch.setattr(app_module.subprocess, "Popen", popen)
    monkeypatch.delenv("FLOATING_CLOCK_DETACHED", raising=False)
    monkeypatch.delattr(sys, "frozen", raising=False)
    monkeypatch.setattr(sys, "argv", ["floating-clock", "--x"])
    assert app_module._detach_to_background() is True
    args, kwargs = popen.call_args
    assert args[0][1:] == ["-m", "floating_clock", "--x"]
    assert kwargs["env"]["FLOATING_CLOCK_DETACHED"] == "1"


def test_detach_skipped_in_child(monkeypatch):
    popen = Mock()
    monkeypatch.setattr(app_module.subprocess, "Popen", popen)
    monkeypatch.setenv("FLOATING_CLOCK_DETACHED", "1")
    assert app_module._detach_to_background() is False
    popen.assert_not_called()
