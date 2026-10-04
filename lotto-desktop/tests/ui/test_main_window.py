from lotto_lab.ui.main_window import MainWindow
from lotto_lab.ui.pages import PAGE_DEFINITIONS
from lotto_lab.persistence.bootstrap import seed_application_data
from lotto_lab.persistence.database import Database
from lotto_lab.ui.feature_pages import AnalyticsPage, DrawHistoryPage, GeneratorPage


def test_main_window_exposes_all_primary_destinations(qapp) -> None:
    window = MainWindow()

    assert window.page_stack.count() == len(PAGE_DEFINITIONS)
    assert len(window.navigation.buttons()) == len(PAGE_DEFINITIONS)
    assert window.page_stack.currentIndex() == 0

    window.show_page(5)
    assert window.page_stack.currentIndex() == 5
    assert window.navigation.button(5).isChecked()

    window.close()


def test_main_window_activates_phase_two_to_four_pages(qapp, tmp_path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'ui.sqlite3').as_posix()}")
    database.create_schema()
    seed_application_data(database)

    window = MainWindow(database)

    assert isinstance(window.page_stack.widget(1), GeneratorPage)
    assert isinstance(window.page_stack.widget(2), DrawHistoryPage)
    assert isinstance(window.page_stack.widget(3), AnalyticsPage)
    assert window.results_sync is not None
    generator = window.page_stack.widget(1)
    generator.count_spin.setValue(1)
    generator.generate()
    from tests.ui.test_phase_workflows import wait_until
    wait_until(qapp, lambda: not generator.job.running)
    assert "Generated and saved 1" in generator.status.text()

    window.close()
    database.dispose()


def test_today_quick_pick_opens_existing_generator(qapp, tmp_path) -> None:
    from datetime import datetime
    from zoneinfo import ZoneInfo
    from lotto_lab.schedule import ScheduleService
    from lotto_lab.domain import GameCode

    database = Database(f"sqlite:///{(tmp_path / 'today.sqlite3').as_posix()}")
    database.create_schema()
    seed_application_data(database)
    window = MainWindow(database)
    today = window.today_page
    today.refresh(datetime(2026, 9, 30, 12, tzinfo=ZoneInfo("Asia/Manila")))
    assert today.date_label.text().startswith("Wednesday, September 30, 2026")
    today.pick_requested.emit(GameCode.GRAND_LOTTO_6_55)
    assert window.page_stack.currentIndex() == 1
    assert window.page_stack.widget(1).game_combo.currentData() == GameCode.GRAND_LOTTO_6_55
    window.close()
    database.dispose()
