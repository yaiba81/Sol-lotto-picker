"""Background historical comparisons with inspectable persisted results."""
from datetime import date, timedelta
from PySide6.QtCore import Qt, QDate
from PySide6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QFormLayout,
    QComboBox, QDateEdit, QSpinBox, QLineEdit, QListWidget, QListWidgetItem,
    QPushButton, QLabel, QProgressBar, QTableWidget, QTabWidget,
    QScrollArea)
from lotto_lab.analytics.service import AnalyticsService
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.strategy.repository import StrategyRepository
from lotto_lab.backtesting.repository import BacktestRepository
from lotto_lab.backtesting.service import BacktestRequest, BacktestService
from lotto_lab.ui.feature_pages import add_page_header, populate_games
from lotto_lab.ui.jobs import JobController
from lotto_lab.ui.charts import HistoryChart
from lotto_lab.ui.paged_table import PagedTable


class BacktestPage(QWidget):
    def __init__(self, database, parent=None):
        super().__init__(parent)
        self.setObjectName("backtesting")
        self.strategies = StrategyRepository(database)
        self.repository = BacktestRepository(database)
        draws = DrawRepository(database)
        self.service = BacktestService(draws, AnalyticsService(draws), self.repository)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        add_page_header(layout, "Backtesting", "Compare observed matches using only draws before each target date. Historical results do not establish improved winning odds.")
        tabs = QTabWidget()
        setup_scroll = QScrollArea()
        setup_scroll.setWidgetResizable(True)
        setup = QWidget()
        form = QFormLayout(setup)
        form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.game_combo = QComboBox()
        populate_games(self.game_combo)
        self.first_date = QDateEdit(QDate.currentDate().addYears(-1))
        self.last_date = QDateEdit(QDate.currentDate())
        for control in (self.first_date, self.last_date):
            control.setCalendarPopup(True)
            control.setDisplayFormat("yyyy-MM-dd")
            control.setMaximumDate(QDate.currentDate())
        self.window_spin = QSpinBox()
        self.window_spin.setRange(1, 10000)
        self.window_spin.setValue(100)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 10000)
        self.count_spin.setValue(100)
        self.seed = QLineEdit("42")
        self.versions = QListWidget()
        self.versions.setMinimumHeight(160)
        for label, control in (("Game", self.game_combo), ("First target date", self.first_date),
                ("Last target date", self.last_date), ("Historical window per game", self.window_spin),
                ("Tickets per target / strategy", self.count_spin), ("Random seed", self.seed),
                ("Strategies (Space to toggle)", self.versions)):
            control.setAccessibleName(label)
            form.addRow(label, control)
        setup_scroll.setWidget(setup)
        tabs.addTab(setup_scroll, "Configure")
        self.table = QTableWidget(0, 11)
        self.table.setHorizontalHeaderLabels(["Strategy", "Tickets"] + [f"{i} matches" for i in range(7)] + ["Mean", "Variance"])
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setAlternatingRowColors(True)
        self.paged_table = PagedTable(self.table)
        tabs.addTab(self.paged_table, "Results table")
        self.chart = HistoryChart()
        tabs.addTab(self.chart, "Comparison chart")
        self.pattern_table = QTableWidget(0, 4)
        self.pattern_table.setHorizontalHeaderLabels(("Strategy", "Generated range pattern", "Tickets", "Share"))
        self.pattern_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.pattern_paged = PagedTable(self.pattern_table)
        tabs.addTab(self.pattern_paged, "Generated patterns")
        self.tabs = tabs
        layout.addWidget(tabs, 1)
        self.runs = QComboBox()
        self.runs.setAccessibleName("Saved backtest runs")
        self.runs.currentIndexChanged.connect(self.load_run)
        layout.addWidget(self.runs)
        self.status = QLabel("Ready. Pure Random v1 is selected as the control.")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.progress_bar = QProgressBar()
        layout.addWidget(self.progress_bar)
        buttons = QHBoxLayout()
        self.start_button = QPushButton("Run backtest")
        self.start_button.setObjectName("primaryButton")
        self.cancel_button = QPushButton("Cancel run")
        self.cancel_button.setEnabled(False)
        buttons.addWidget(self.start_button)
        buttons.addWidget(self.cancel_button)
        layout.addLayout(buttons)
        self.job = JobController(self)
        self.job.result.connect(self.show_report)
        self.job.error.connect(lambda message: self.status.setText(f"Backtest failed: {message}"))
        self.job.progress.connect(self.on_progress)
        self.job.finished.connect(self.on_finished)
        self.start_button.clicked.connect(self.start)
        self.cancel_button.clicked.connect(self.cancel)
        self.refresh_versions()
        self.refresh_runs()

    def refresh_versions(self):
        checked = {self.versions.item(i).data(Qt.ItemDataRole.UserRole)
                   for i in range(self.versions.count()) if self.versions.item(i).checkState() == Qt.CheckState.Checked}
        self.versions.clear()
        for identifier, label in self.strategies.list_versions():
            item = QListWidgetItem(label)
            item.setData(Qt.ItemDataRole.UserRole, identifier)
            item.setFlags(item.flags() | Qt.ItemFlag.ItemIsUserCheckable)
            item.setCheckState(Qt.CheckState.Checked if identifier in checked or label == "Pure Random v1" else Qt.CheckState.Unchecked)
            self.versions.addItem(item)

    def start(self):
        try:
            ids = tuple(self.versions.item(i).data(Qt.ItemDataRole.UserRole) for i in range(self.versions.count())
                        if self.versions.item(i).checkState() == Qt.CheckState.Checked)
            request = BacktestRequest(self.game_combo.currentData(), self.first_date.date().toPython(),
                self.last_date.date().toPython(), ids, self.count_spin.value(), self.window_spin.value(), int(self.seed.text()))
        except ValueError as exc:
            self.status.setText(str(exc))
            return
        if self.job.start(lambda cancel, progress: self.service.run(request, cancel, progress)):
            self.start_button.setEnabled(False)
            self.cancel_button.setEnabled(True)
            self.runs.setEnabled(False)
            self.tabs.widget(0).setEnabled(False)
            self.progress_bar.setValue(0)
            self.status.setText("Running chronological simulation...")

    def cancel(self):
        self.job.cancel()
        self.status.setText("Cancelling; partial results will be retained.")
        self.cancel_button.setEnabled(False)

    def on_progress(self, done, total):
        self.progress_bar.setRange(0, total)
        self.progress_bar.setValue(done)

    def on_finished(self):
        self.start_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        self.runs.setEnabled(True)
        self.tabs.widget(0).setEnabled(True)
        self.refresh_runs()

    def refresh_runs(self):
        self.runs.blockSignals(True)
        self.runs.clear()
        for identifier, label in self.repository.list_runs():
            self.runs.addItem(label, identifier)
        self.runs.blockSignals(False)

    def load_run(self):
        if self.runs.currentData() is not None:
            self.show_report(self.repository.report(self.runs.currentData()))

    def show_report(self, report):
        self.status.setText(f"Run #{report.run_id}: {report.status}. " +
            ("Partial results; workloads may differ between strategies." if report.status != "completed" else "Descriptive mean and population variance of matches per ticket."))
        self.paged_table.set_rows(tuple(
            (result.label, sum(result.counts), *result.counts,
             f"{result.mean:.4f}", f"{result.variance:.4f}")
            for result in report.results
        ))
        self.table.resizeColumnsToContents()
        self.pattern_paged.set_rows(tuple(
            (result.label, pattern, count, f"{100 * count / sum(result.counts):.2f}%")
            for result in report.results
            for pattern, count in sorted(result.range_patterns.items(), key=lambda item: (-item[1], item[0]))
            if sum(result.counts)
        ))
        self.pattern_table.resizeColumnsToContents()
        self.status.setText(self.status.text() + " " + " | ".join(
            f"{result.label}: {len(result.range_patterns)} distinct generated patterns"
            if result.range_patterns else f"{result.label}: no recorded pattern observations (older runs may lack these)"
            for result in report.results))
        self.chart.comparison(report.results)
        self.tabs.setCurrentIndex(1)
