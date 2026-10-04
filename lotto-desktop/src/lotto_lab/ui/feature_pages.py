from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import Qt, Signal
from PySide6.QtWidgets import (
    QComboBox,
    QTabWidget,
    QFileDialog,
    QFormLayout,
    QFrame,
    QGridLayout,
    QGroupBox,
    QHBoxLayout,
    QLabel,
    QMessageBox,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QTableWidget,
    QVBoxLayout,
    QWidget,
)

from lotto_lab.analytics.service import AnalyticsService
from lotto_lab.domain import GameCode, SUPPORTED_GAMES
from lotto_lab.draw_history import DrawCsvImporter, DrawRepository
from lotto_lab.generator.models import GeneratedCombination
from lotto_lab.generator.repository import TicketRepository
from lotto_lab.generator.service import GeneratorService
from lotto_lab.persistence.database import Database
from lotto_lab.strategy.repository import StrategyRepository
from lotto_lab.ui.jobs import JobController
from lotto_lab.ui.charts import HistoryChart
from lotto_lab.ui.paged_table import PagedTable
from lotto_lab.ui.range_analysis import RangeAnalysisPanel


def add_page_header(layout: QVBoxLayout, title: str, description: str) -> None:
    eyebrow = QLabel("LOTTO LAB")
    eyebrow.setObjectName("eyebrow")
    heading = QLabel(title)
    heading.setObjectName("pageTitle")
    details = QLabel(description)
    details.setObjectName("pageDescription")
    details.setWordWrap(True)
    layout.addWidget(eyebrow)
    layout.addWidget(heading)
    layout.addWidget(details)
    layout.addSpacing(12)


def populate_games(combo: QComboBox) -> None:
    for game in SUPPORTED_GAMES:
        combo.addItem(game.name, game.code)


class DrawHistoryPage(QWidget):
    sync_requested = Signal()

    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("draw_history")
        self.repository = DrawRepository(database)
        self.importer = DrawCsvImporter()

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)
        add_page_header(layout, "Draw History", "Import and inspect validated historical draw results.")

        actions = QHBoxLayout()
        self.game_filter = QComboBox()
        self.game_filter.addItem("All games", None)
        populate_games(self.game_filter)
        self.game_filter.currentIndexChanged.connect(self.refresh)
        self.import_button = QPushButton("Import CSV")
        self.import_button.setObjectName("primaryButton")
        self.import_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.import_button.clicked.connect(self.choose_csv)
        self.sync_button = QPushButton("Check official results")
        self.sync_button.setObjectName("primaryButton")
        self.sync_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.sync_button.clicked.connect(self.sync_requested.emit)
        actions.addWidget(QLabel("Game"))
        actions.addWidget(self.game_filter)
        actions.addStretch()
        actions.addWidget(self.import_button)
        actions.addWidget(self.sync_button)
        layout.addLayout(actions)

        self.status = QLabel()
        self.status.setObjectName("statusMessage")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(("Date", "Game", "Numbers"))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.setSelectionBehavior(QTableWidget.SelectionBehavior.SelectRows)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.paged_table = PagedTable(self.table)
        layout.addWidget(self.paged_table, 1)
        self.refresh()

    def choose_csv(self) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "Import historical draws", "", "CSV files (*.csv)")
        if path:
            self.import_path(Path(path))

    def import_path(self, path: Path) -> None:
        try:
            result = self.importer.parse(path)
            inserted = self.repository.add_many(result.draws, source=str(path))
        except (OSError, ValueError) as exc:
            self.status.setText(f"Import failed: {exc}")
            QMessageBox.warning(self, "Import failed", str(exc))
            return
        message = f"Imported {inserted} new draw(s)."
        if result.issues:
            message += f" Skipped {len(result.issues)} invalid row(s); first issue: row {result.issues[0].row_number}: {result.issues[0].message}"
        self.status.setText(message)
        self.refresh()

    def refresh(self) -> None:
        selected = self.game_filter.currentData()
        total = self.repository.count(selected)

        def load_page(offset: int, limit: int) -> tuple[tuple[str, str, str], ...]:
            draws = self.repository.list_draws(
                game_code=selected, limit=limit, offset=offset, newest_first=True
            )
            return tuple((draw.draw_date.isoformat(), draw.game_code.value,
                "  ".join(f"{n:02d}" for n in sorted(draw.numbers))) for draw in draws)

        self.paged_table.set_source(total, load_page)
        if not self.status.text():
            self.status.setText(f"{total} stored draw(s). CSV format: game,date,n1,n2,n3,n4,n5,n6")

    def set_sync_status(self, message: str) -> None:
        self.status.setText(message)
        self.sync_button.setEnabled("checking" not in message.casefold())


class AnalyticsPage(QWidget):
    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("analytics")
        self.analytics = AnalyticsService(DrawRepository(database))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)
        add_page_header(layout, "Analytics", "Point-in-time summaries of historical characteristics.")

        form = QGridLayout()
        self.game_combo = QComboBox()
        populate_games(self.game_combo)
        self.window_spin = QSpinBox()
        self.window_spin.setRange(1, 10000)
        self.window_spin.setValue(100)
        refresh = QPushButton("Refresh analysis")
        refresh.setObjectName("primaryButton")
        refresh.setCursor(Qt.CursorShape.PointingHandCursor)
        refresh.clicked.connect(self.refresh)
        self.refresh_button = refresh
        self.game_combo.setMinimumContentsLength(12)
        self.game_combo.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        game_label = QLabel("Game")
        game_label.setBuddy(self.game_combo)
        window_label = QLabel("Historical window")
        window_label.setBuddy(self.window_spin)
        form.addWidget(game_label, 0, 0)
        form.addWidget(self.game_combo, 1, 0)
        form.addWidget(window_label, 0, 1)
        form.addWidget(self.window_spin, 1, 1)
        form.addWidget(refresh, 1, 2)
        layout.addLayout(form)

        self.summary = QLabel()
        self.summary.setObjectName("notice")
        self.summary.setWordWrap(True)
        layout.addWidget(self.summary)
        self.table = QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(("Characteristic", "Category", "Draws"))
        self.table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setStretchLastSection(True)
        self.tabs = QTabWidget()
        chart_panel = QWidget()
        chart_layout = QVBoxLayout(chart_panel)
        self.chart_kind = QComboBox()
        self.chart_kind.addItems(("Number frequency", "Cross-game presence", "Consecutive runs", "Group concentration", "Odd / even"))
        self.chart_kind.setAccessibleName("Historical chart characteristic")
        self.chart = HistoryChart()
        chart_layout.addWidget(self.chart_kind)
        chart_layout.addWidget(self.chart)
        chart_panel.setMinimumHeight(380)
        chart_scroll = QScrollArea()
        chart_scroll.setWidgetResizable(True)
        chart_scroll.setWidget(chart_panel)
        self.tabs.addTab(chart_scroll, "Charts")
        self.paged_table = PagedTable(self.table)
        self.tabs.addTab(self.paged_table, "Data table")
        self.range_panel = RangeAnalysisPanel()
        self.tabs.addTab(self.range_panel, "Range Analysis")
        self.tabs.currentChanged.connect(lambda index: self.summary.setVisible(index != 2))
        layout.addWidget(self.tabs, 1)
        self.snapshot_data = None
        self.chart_kind.currentIndexChanged.connect(self.render_chart)
        self.job = JobController(self)
        self.job.result.connect(self.show_snapshot)
        self.job.error.connect(lambda message: self.summary.setText(f"Analysis failed: {message}"))
        self.job.finished.connect(lambda: self.refresh_button.setEnabled(True))
        self.job.finished.connect(lambda: self.game_combo.setEnabled(True))
        self.job.finished.connect(lambda: self.window_spin.setEnabled(True))
        self.analysis_window = self.window_spin.value()
        self.summary.setText("Select Refresh analysis to inspect local history.")

    def refresh(self) -> None:
        game, window = self.game_combo.currentData(), self.window_spin.value()
        if self.job.start(lambda cancel, progress: self.analytics.snapshot(game, window=window)):
            self.analysis_window = window
            self.game_combo.setEnabled(False)
            self.window_spin.setEnabled(False)
            self.refresh_button.setEnabled(False)
            self.summary.setText("Analyzing local history...")

    def show_snapshot(self, snapshot) -> None:
        self.snapshot_data = snapshot
        self.range_panel.show_snapshot(snapshot, self.analysis_window)
        top = sorted(snapshot.number_frequencies.items(), key=lambda item: (-item[1], item[0]))[:10]
        top_text = ", ".join(f"{number:02d} ({count})" for number, count in top)
        self.summary.setText(
            f"Analyzed {snapshot.draw_count} draw(s). Most frequent in this window: {top_text or 'no historical data yet'}. "
            "Frequency describes history only; it is not a prediction."
        )
        rows: list[tuple[str, str, int]] = []
        rows.extend(("Number frequency", str(key), count) for key, count in snapshot.number_frequencies.items())
        rows.extend(("Cross-game presence", str(key), count) for key, count in snapshot.cross_game_occurrences.items())
        rows.extend(("Consecutive run", key, count) for key, count in snapshot.sequence_distribution.items())
        rows.extend(("Maximum group concentration", str(key), count) for key, count in snapshot.bucket_distribution.items())
        rows.extend(("Odd / even split", f"{key}/{6-key}", count) for key, count in snapshot.odd_even_distribution.items())
        self.paged_table.set_rows(rows)

        self.render_chart()

    def render_chart(self):
        snapshot = self.snapshot_data
        if snapshot is None:
            return
        options = (
            (snapshot.number_frequencies, "Number", "Occurrences"),
            (snapshot.cross_game_occurrences, "Number", "Games containing number"),
            (snapshot.sequence_distribution, "Longest consecutive run", "Draws"),
            (snapshot.bucket_distribution, "Maximum numbers in one group", "Draws"),
            ({f"{key}/{6-key}": value for key, value in snapshot.odd_even_distribution.items()}, "Odd / even split", "Draws"),
        )
        values, xlabel, ylabel = options[self.chart_kind.currentIndex()]
        self.chart.bars(self.chart_kind.currentText(), list(values), list(values.values()), xlabel, ylabel)


class TicketCard(QGroupBox):
    def __init__(self, combination: GeneratedCombination, parent: QWidget | None = None) -> None:
        super().__init__(combination.strategy_label, parent)
        layout = QVBoxLayout(self)
        numbers = QHBoxLayout()
        numbers.addStretch()
        for number in combination.numbers:
            ball = QLabel(f"{number:02d}")
            ball.setObjectName("numberBall")
            ball.setAlignment(Qt.AlignmentFlag.AlignCenter)
            numbers.addWidget(ball)
        numbers.addStretch()
        layout.addLayout(numbers)
        score = QLabel(f"Historical pattern score: {combination.historical_pattern_score:.1f}/100")
        score.setObjectName("scoreLabel")
        score.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(score)
        factors = "  ·  ".join(
            f"{name.replace('_', ' ').title()}: {value:.3f}"
            for name, value in combination.summary_factors.items()
        )
        factor_label = QLabel(factors)
        factor_label.setWordWrap(True)
        factor_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        layout.addWidget(factor_label)
        details = QLabel(
            "\n".join(
                f"{item.number:02d} — weight {item.final_weight:.4f}: {'; '.join(item.explanations)}"
                for item in combination.selected_evaluations
            )
        )
        details.setObjectName("ticketDetails")
        details.setWordWrap(True)
        details.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        details.setVisible(False)
        toggle = QPushButton("Show weight explanation")
        toggle.setObjectName("linkButton")
        toggle.setCheckable(True)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        toggle.toggled.connect(details.setVisible)
        toggle.toggled.connect(
            lambda checked: toggle.setText("Hide weight explanation" if checked else "Show weight explanation")
        )
        layout.addWidget(toggle)
        layout.addWidget(details)


class GeneratorPage(QWidget):
    def __init__(self, database: Database, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("generator")
        repository = DrawRepository(database)
        self.strategies = StrategyRepository(database)
        self.service = GeneratorService(
            AnalyticsService(repository), self.strategies, TicketRepository(database)
        )

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 30, 40, 30)
        layout.setSpacing(12)
        add_page_header(
            layout,
            "Ticket Generator",
            "Generate independent random combinations with optional, explainable historical weighting.",
        )

        panel = QFrame()
        panel.setObjectName("controlPanel")
        form = QGridLayout(panel)
        self.game_combo = QComboBox()
        populate_games(self.game_combo)
        self.strategy_combo = QComboBox()
        for identifier, label in self.strategies.list_versions():
            self.strategy_combo.addItem(label, identifier)
        self.window_spin = QSpinBox()
        self.window_spin.setRange(1, 10000)
        self.window_spin.setValue(100)
        self.count_spin = QSpinBox()
        self.count_spin.setRange(1, 100)
        self.count_spin.setValue(5)
        controls = (
            ("Game", self.game_combo),
            ("Strategy", self.strategy_combo),
            ("Historical window", self.window_spin),
            ("Number of tickets", self.count_spin),
        )
        for column, (text, control) in enumerate(controls):
            label = QLabel(text)
            label.setBuddy(control)
            form.addWidget(label, 0, column)
            form.addWidget(control, 1, column)
        self.generate_button = QPushButton("Generate tickets")
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.generate_button.clicked.connect(self.generate)
        form.addWidget(self.generate_button, 1, len(controls))
        layout.addWidget(panel)

        disclaimer = QLabel(
            "Each valid combination remains possible. Historical weighting is an experiment and does not increase or guarantee winning probability."
        )
        disclaimer.setObjectName("notice")
        disclaimer.setWordWrap(True)
        layout.addWidget(disclaimer)
        self.status = QLabel("Ready to generate.")
        self.status.setObjectName("statusMessage")
        layout.addWidget(self.status)

        self.results_widget = QWidget()
        self.results_layout = QVBoxLayout(self.results_widget)
        self.results_layout.setContentsMargins(0, 0, 8, 0)
        self.results_layout.setSpacing(12)
        self.results_layout.addStretch()
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setWidget(self.results_widget)
        layout.addWidget(scroll, 1)

        self.job = JobController(self)
        self.job.result.connect(self.show_combinations)
        self.job.error.connect(lambda message: self.status.setText(f"Generation failed: {message}"))
        self.job.finished.connect(lambda: self.generate_button.setEnabled(True))

    def generate(self) -> None:
        arguments = dict(game_code=self.game_combo.currentData(),
            strategy_version_id=self.strategy_combo.currentData(), window=self.window_spin.value(),
            ticket_count=self.count_spin.value())
        if self.job.start(lambda cancel, progress: self.service.generate(**arguments)):
            self.generate_button.setEnabled(False)
            self.status.setText("Generating and saving tickets...")

    def show_combinations(self, combinations) -> None:
        while self.results_layout.count() > 1:
            item = self.results_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for combination in combinations:
            self.results_layout.insertWidget(self.results_layout.count() - 1, TicketCard(combination))
        self.status.setText(f"Generated and saved {len(combinations)} ticket(s) locally.")
