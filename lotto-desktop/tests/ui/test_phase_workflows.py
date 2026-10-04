from time import monotonic
from threading import Event
from PySide6.QtCore import QThread, Qt
from PySide6.QtTest import QTest
from lotto_lab.ui.jobs import JobController
from lotto_lab.ui.main_window import MainWindow
from lotto_lab.ui.strategy_page import StrategyLabPage
from lotto_lab.ui.backtest_page import BacktestPage
from lotto_lab.ui.theme import APP_STYLESHEET


def wait_until(qapp, condition, timeout=10):
    deadline = monotonic() + timeout
    while not condition():
        qapp.processEvents()
        QTest.qWait(5)
        assert monotonic() < deadline, "Background job timed out"
    qapp.processEvents()


def test_worker_progress_cancel_and_gui_delivery(qapp):
    job = JobController()
    entered = Event()
    deliveries = []
    def operation(cancel, progress):
        assert QThread.currentThread() != qapp.thread()
        entered.set()
        progress(1, 10)
        cancel.wait(2)
        return cancel.is_set()
    job.result.connect(lambda result: deliveries.append((result, QThread.currentThread())))
    progress = []
    job.progress.connect(lambda done, total: progress.append((done,total)))
    assert job.start(operation)
    assert not job.start(operation)
    wait_until(qapp, entered.is_set)
    job.cancel()
    wait_until(qapp, lambda: not job.running)
    assert deliveries == [(True, qapp.thread())]
    assert progress == [(1,10)]


def test_phase_pages_keyboard_charts_and_resize(qapp, db, tmp_path):
    qapp.setStyleSheet(APP_STYLESHEET)
    window = MainWindow(db)
    window.resize(900, 600)
    window.show()
    lab = window.page_stack.widget(4)
    backtest = window.page_stack.widget(5)
    assert isinstance(lab, StrategyLabPage)
    assert isinstance(backtest, BacktestPage)
    window.show_page(4)
    lab.clone_button.setFocus()
    QTest.keyClick(lab.clone_button, Qt.Key.Key_Space)
    assert lab.versions.currentText().endswith(" v2")
    assert lab.save_button.isEnabled()
    lab.controls["frequency_strength"].setValue(0.7)
    lab.save_version()
    assert "saved" in lab.status.text()
    window.show_page(1)
    assert window.page_stack.widget(1).strategy_combo.findText(lab.versions.currentText()) >= 0
    window.show_page(3)
    analytics = window.page_stack.widget(3)
    analytics.refresh()
    wait_until(qapp, lambda: not analytics.job.running)
    assert analytics.snapshot_data.draw_count == 0
    for index in range(5):
        analytics.chart_kind.setCurrentIndex(index)
        analytics.chart.canvas.draw()
        assert analytics.chart.figure.axes[0].get_xlabel()
    for index in (3,4,5):
        window.show_page(index)
        qapp.processEvents()
        assert window.width() == 900
        assert window.page_stack.widget(index).width() >= 600
    window.close()


def test_backtest_ui_runs_and_reloads(qapp, db):
    from datetime import date
    from PySide6.QtCore import QDate
    from lotto_lab.domain import GameCode, HistoricalDraw
    from lotto_lab.draw_history.repository import DrawRepository
    DrawRepository(db).add_many((HistoricalDraw(GameCode.LOTTO_6_42, date(2025,1,2), (1,2,3,4,5,6)),))
    page = BacktestPage(db)
    page.first_date.setDate(QDate(2025,1,1))
    page.last_date.setDate(QDate(2025,1,3))
    page.count_spin.setValue(3)
    page.start()
    assert not page.start_button.isEnabled()
    wait_until(qapp, lambda: not page.job.running)
    assert "completed" in page.status.text()
    assert page.table.rowCount() == 1
    assert page.table.item(0,1).text() == "3"
    assert page.runs.count() == 1
    page.load_run()
    assert "completed" in page.status.text()
    page.chart.canvas.draw()
    assert len(page.chart.figure.axes[0].lines) == 1
    page.close()
