from datetime import date, timedelta

from PySide6.QtCore import Qt
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QTableWidget

from lotto_lab.domain import GameCode, HistoricalDraw
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.ui.feature_pages import DrawHistoryPage, AnalyticsPage
from lotto_lab.ui.backtest_page import BacktestPage
from lotto_lab.ui.paged_table import PagedTable
from lotto_lab.backtesting.service import BacktestReport, StrategyResult


def test_page_boundaries_keyboard_size_and_reset(qapp):
    table = QTableWidget(0, 1)
    pager = PagedTable(table)
    pager.resize(600, 400)
    pager.show()
    assert pager.summary.text() == "No rows"
    assert not pager.previous.isEnabled() and not pager.next.isEnabled()
    assert not pager.page.isEnabled()
    pager.set_rows([(i,) for i in range(53)])
    assert table.rowCount() == 25
    assert pager.summary.text() == "Rows 1-25 of 53"
    pager.next.setFocus()
    QTest.keyClick(pager.next, Qt.Key.Key_Space)
    assert table.item(0, 0).text() == "25"
    assert table.verticalHeaderItem(0).text() == "26"
    pager.page.setValue(3)
    assert table.rowCount() == 3
    assert table.item(2, 0).text() == "52"
    assert not pager.next.isEnabled()
    pager.previous.click()
    assert pager.page.value() == 2
    pager.page_size.setCurrentText("10")
    assert pager.page.value() == 1
    assert pager.page.maximum() == 6
    assert table.rowCount() == 10
    pager.page.setValue(6)
    pager.set_rows([("new result",)])
    assert pager.page.value() == 1
    assert table.item(0, 0).text() == "new result"
    pager.set_rows([])
    assert table.rowCount() == 0
    assert pager.summary.text() == "No rows"
    pager.close()


def test_history_pages_beyond_500_and_resets_filter(qapp, db):
    repository = DrawRepository(db)
    repository.add_many(tuple(HistoricalDraw(GameCode.LOTTO_6_42,
        date(2020, 1, 1) + timedelta(days=i), (1,2,3,4,5,6)) for i in range(503)))
    page = DrawHistoryPage(db)
    pager = page.paged_table
    assert page.table.rowCount() == 25
    assert pager.total == 503
    pager.page.setValue(21)
    assert page.table.rowCount() == 3
    assert page.table.item(2, 0).text() == "2020-01-01"
    page.game_filter.setCurrentIndex(2)
    assert pager.page.value() == 1
    assert pager.total == 0
    assert page.table.rowCount() == 0
    page.game_filter.setCurrentIndex(1)
    assert pager.total == 503
    assert page.table.rowCount() == 25
    page.close()


def test_analytics_and_backtest_paging_preserve_all_chart_data(qapp, db):
    analytics = AnalyticsPage(db)
    snapshot = analytics.analytics.snapshot(GameCode.LOTTO_6_42)
    analytics.show_snapshot(snapshot)
    assert analytics.table.rowCount() == 25
    assert analytics.paged_table.total > 42
    analytics.paged_table.next.click()
    assert analytics.table.item(0, 1).text() == "26"
    assert len(analytics.chart.figure.axes[0].patches) == 42
    analytics.show_snapshot(snapshot)
    assert analytics.paged_table.page.value() == 1
    page = BacktestPage(db)
    results = tuple(StrategyResult.from_counts(i, f"Experiment v{i}", (1,0,0,0,0,0,0))
                    for i in range(1, 28))
    page.show_report(BacktestReport(1, "completed", results))
    assert page.table.rowCount() == 25
    page.paged_table.next.click()
    assert page.table.rowCount() == 2
    assert page.table.item(0, 0).text() == "Experiment v26"
    assert len(page.chart.figure.axes[0].lines) == 27
    page.close()
    analytics.close()
