from __future__ import annotations

import os

import pytest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


@pytest.fixture(scope="session")
def qapp():
    pytest.importorskip("PySide6")
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])



@pytest.fixture
def db(tmp_path):
    from lotto_lab.persistence.database import Database
    from lotto_lab.persistence.bootstrap import seed_application_data
    database = Database(f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    database.create_schema()
    seed_application_data(database)
    yield database
    database.dispose()


@pytest.fixture(autouse=True)
def cleanup_qt_widgets():
    yield
    import gc
    from PySide6.QtCore import QCoreApplication, QEvent
    from PySide6.QtWidgets import QApplication
    app = QApplication.instance()
    if app is not None:
        for widget in app.topLevelWidgets():
            widget.close()
            widget.deleteLater()
        QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
        app.processEvents()
        gc.collect()
