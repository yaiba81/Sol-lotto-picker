from datetime import date
from time import monotonic

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest

from lotto_lab.domain import GameCode, HistoricalDraw
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.strategy.config import JONATHAN_RANGE_CONFIG
from lotto_lab.ui.feature_pages import AnalyticsPage
from lotto_lab.ui.strategy_page import StrategyLabPage
from lotto_lab.ui.theme import APP_STYLESHEET


def wait(qapp, job):
    deadline = monotonic() + 10
    while job.running:
        qapp.processEvents()
        QTest.qWait(5)
        assert monotonic() < deadline
    qapp.processEvents()


def test_range_ui_worker_tables_chart_keyboard_and_game_window(qapp, db):
    qapp.setStyleSheet(APP_STYLESHEET)
    DrawRepository(db).add_many((
        HistoricalDraw(GameCode.ULTRA_LOTTO_6_58, date(2025,1,1), (1,2,3,4,5,6)),
        HistoricalDraw(GameCode.ULTRA_LOTTO_6_58, date(2025,1,2), (12,24,36,43,47,55))))
    page = AnalyticsPage(db)
    page.resize(900, 600)
    page.show()
    page.game_combo.setCurrentIndex(4)
    page.window_spin.setValue(1)
    page.tabs.setCurrentIndex(2)
    page.refresh_button.setFocus()
    QTest.keyClick(page.refresh_button, Qt.Key.Key_Space)
    assert not page.refresh_button.isEnabled()
    wait(qapp, page.job)
    panel = page.range_panel
    assert "6/58" in panel.context.text() and "latest 1 draws" in panel.context.text()
    assert panel.frequency_table.rowCount() == 6
    assert panel.frequency_table.item(0,0).text() == "1-9"
    assert panel.pattern_table.item(0,0).text() == "0-1-1-1-2-1"
    panel.tabs.setCurrentIndex(1)
    panel.order.setFocus()
    QTest.keyClick(panel.order, Qt.Key.Key_End)
    assert panel.patterns.total == 462
    panel.patterns.next.click()
    assert panel.patterns.page.value() == 2
    panel.tabs.setCurrentIndex(3)
    panel.chart.canvas.draw()
    assert len(panel.chart.figure.axes[0].patches) == 12
    page.game_combo.setCurrentIndex(0)
    page.refresh()
    wait(qapp, page.job)
    assert panel.frequency_table.rowCount() == 5
    assert panel.frequency_table.item(0,4).text() == "No observations"
    assert panel.patterns.page.value() == 1
    assert len(panel.statistics.high_numbers) == 1
    assert page.width() == 900
    page.close()


def test_range_controls_save_percentage_and_lock(qapp, db):
    page = StrategyLabPage(db)
    enhanced = next(i for i, _ in page.repository.list_versions() if page.repository.get_config(i)[1] == JONATHAN_RANGE_CONFIG)
    page.versions.setCurrentIndex(page.versions.findData(enhanced))
    assert page.controls["range_strength"].value() == 20
    assert page.controls["use_range"].isChecked()
    assert not page.save_button.isEnabled()
    page.clone_version()
    page.show()
    control = page.controls["use_range"]
    control.setFocus()
    QTest.keyClick(control, Qt.Key.Key_Space)
    assert not control.isChecked()
    page.controls["range_strength"].setValue(35)
    page.save_version()
    config = page.repository.get_config(page.versions.currentData())[1]
    assert config.range_strength == 0.35 and not config.use_range
    assert config.use_high_number_balance
    page.repository.acquire_config(page.versions.currentData())
    page.load_version()
    assert not page.controls["range_strength"].isEnabled()
    page.close()
