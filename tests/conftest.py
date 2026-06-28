"""Shared test fixtures.

Note: before importing any PySide6 module, the Qt platform must be set to
offscreen, so CI / headless environments can create a QApplication and build
widgets.
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """A single QApplication instance shared by the whole test session.

    A Qt process can only have one QApplication; creating another raises, so
    use a session singleton.
    """
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def temp_config_dir(monkeypatch):
    """Redirect the config file to a temp dir, isolating the real config/config.ini."""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.ini"
        monkeypatch.setattr("floating_clock.config.config_path", lambda: path)
        yield tmpdir
