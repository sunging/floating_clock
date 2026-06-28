"""共享测试 fixture。

注意：在导入任何 PySide6 模块之前，必须先把 Qt 平台设为 offscreen，
这样 CI / 无显示环境也能创建 QApplication 与构造控件。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile  # noqa: E402
from pathlib import Path  # noqa: E402

import pytest  # noqa: E402
from PySide6.QtWidgets import QApplication  # noqa: E402


@pytest.fixture(scope="session")
def qapp():
    """整个测试会话共享一个 QApplication 实例。

    Qt 进程内只能有一个 QApplication，重复创建会报错，故用 session 单例。
    """
    app = QApplication.instance() or QApplication([])
    yield app


@pytest.fixture
def temp_config_dir(monkeypatch):
    """把配置文件重定向到临时目录，隔离真实的 config/config.ini。"""
    with tempfile.TemporaryDirectory() as tmpdir:
        path = Path(tmpdir) / "config.ini"
        monkeypatch.setattr("floating_clock.config.config_path", lambda: path)
        yield tmpdir
