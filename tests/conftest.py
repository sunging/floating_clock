"""共享测试 fixture。

注意：在导入任何 PySide6 模块之前，必须先把 Qt 平台设为 offscreen，
这样 CI / 无显示环境也能创建 QApplication 与构造控件。
"""

import os

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

import tempfile  # noqa: E402

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
def temp_config_dir():
    """切到临时目录运行，隔离 config.ini（其路径取 Path.cwd()）。"""
    old_cwd = os.getcwd()
    with tempfile.TemporaryDirectory() as tmpdir:
        os.chdir(tmpdir)
        try:
            yield tmpdir
        finally:
            os.chdir(old_cwd)
