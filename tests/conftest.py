import sys

import pytest
from PyQt6.QtCore import QCoreApplication


@pytest.fixture(scope="session", autouse=True)
def qt_app():
    """A QCoreApplication instance is required before constructing any QObject
    (QThread subclasses included), even when tests never call exec()."""
    app = QCoreApplication.instance()
    if app is None:
        app = QCoreApplication(sys.argv)
    yield app
