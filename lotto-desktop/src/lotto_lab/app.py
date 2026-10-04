"""Application composition root."""

from __future__ import annotations

import sys
from collections.abc import Sequence

from PySide6.QtWidgets import QApplication
from PySide6.QtCore import QTimer

from lotto_lab.config import APP_NAME, APP_ORGANIZATION, AppSettings
from lotto_lab.persistence.bootstrap import seed_application_data
from lotto_lab.persistence.database import Database
from lotto_lab.ui.main_window import MainWindow
from lotto_lab.ui.theme import APP_STYLESHEET
from lotto_lab.schedule import ScheduleService


def build_database(settings: AppSettings) -> Database:
    settings.ensure_directories()
    database = Database(settings.database_url)
    database.create_schema()
    seed_application_data(database)
    return database


def main(argv: Sequence[str] | None = None) -> int:
    app = QApplication(list(argv) if argv is not None else sys.argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(APP_ORGANIZATION)
    app.setStyleSheet(APP_STYLESHEET)

    settings = AppSettings.load()
    database = build_database(settings)
    app.aboutToQuit.connect(database.dispose)

    window = MainWindow(database, ScheduleService.from_json(settings.data_dir / "lotto_schedule.json"))
    window.show()
    QTimer.singleShot(0, window.start_results_sync)
    return app.exec()
