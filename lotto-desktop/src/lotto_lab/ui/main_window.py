from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtGui import QCloseEvent
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from lotto_lab.ui.pages import PAGE_DEFINITIONS, PhasePage
from lotto_lab.ui.feature_pages import AnalyticsPage, DrawHistoryPage, GeneratorPage
from lotto_lab.persistence.database import Database
from lotto_lab.draw_history import DrawRepository, ResultsSyncService
from lotto_lab.ui.results_sync import ResultsSyncController
from lotto_lab.ui.strategy_page import StrategyLabPage
from lotto_lab.ui.backtest_page import BacktestPage
from lotto_lab.ui.jobs import JobController
from lotto_lab.schedule import ScheduleService
from lotto_lab.domain import GameCode
from lotto_lab.ui.today_page import TodayPage


class MainWindow(QMainWindow):
    """Primary application shell; feature pages plug into its content stack."""

    def __init__(self, database: Database | None = None, schedule: ScheduleService | None = None) -> None:
        super().__init__()
        self.setWindowTitle("Lotto Lab")
        self.resize(1180, 760)
        self.setMinimumSize(900, 600)

        root = QWidget()
        root_layout = QHBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setObjectName("sidebar")
        sidebar.setFixedWidth(220)
        sidebar_layout = QVBoxLayout(sidebar)
        sidebar_layout.setContentsMargins(16, 24, 16, 20)
        sidebar_layout.setSpacing(6)

        brand = QLabel("Lotto Lab")
        brand.setObjectName("brand")
        sidebar_layout.addWidget(brand)

        self.page_stack = QStackedWidget()
        self.results_sync: ResultsSyncController | None = None
        self.draw_history_page: DrawHistoryPage | None = None
        self.today_page: TodayPage | None = None
        self.navigation = QButtonGroup(self)
        self.navigation.setExclusive(True)

        for index, definition in enumerate(PAGE_DEFINITIONS):
            button = QPushButton(definition.label)
            button.setObjectName("navButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(f"Open {definition.label}")
            button.clicked.connect(lambda checked=False, page=index: self.show_page(page))
            self.navigation.addButton(button, index)
            sidebar_layout.addWidget(button)
            if definition.key == "dashboard":
                page_widget = TodayPage(schedule or ScheduleService())
                self.today_page = page_widget
            elif database is not None and definition.key == "generator":
                page_widget = GeneratorPage(database)
            elif database is not None and definition.key == "draw_history":
                page_widget = DrawHistoryPage(database)
                self.draw_history_page = page_widget
            elif database is not None and definition.key == "analytics":
                page_widget = AnalyticsPage(database)
            elif database is not None and definition.key == "strategy_lab":
                page_widget = StrategyLabPage(database)
            elif database is not None and definition.key == "backtesting":
                page_widget = BacktestPage(database)
            else:
                page_widget = PhasePage(definition)
            self.page_stack.addWidget(page_widget)

        sidebar_layout.addStretch()
        disclaimer = QLabel("Historical analysis,\nnot prediction.")
        disclaimer.setStyleSheet("color: #94A3B8; padding: 8px;")
        sidebar_layout.addWidget(disclaimer)

        root_layout.addWidget(sidebar)
        root_layout.addWidget(self.page_stack, 1)
        self.setCentralWidget(root)
        self.statusBar().showMessage("Local database ready")
        self.show_page(0)
        if self.today_page is not None:
            self.today_page.pick_requested.connect(self.open_picker)
            self.today_page.results_requested.connect(lambda: self.show_page(2))
        if database is not None and self.draw_history_page is not None:
            self.results_sync = ResultsSyncController(
                ResultsSyncService(DrawRepository(database)), self
            )
            self.draw_history_page.sync_requested.connect(self.start_results_sync)
            self.results_sync.status_changed.connect(self._show_sync_status)
            self.results_sync.synchronized.connect(lambda _: self.draw_history_page.refresh())

    def show_page(self, index: int) -> None:
        if not 0 <= index < self.page_stack.count():
            raise IndexError(f"Page index out of range: {index}")
        page = self.page_stack.widget(index)
        if isinstance(page, TodayPage):
            page.refresh()
        if isinstance(page, StrategyLabPage):
            page.refresh_versions()
        elif isinstance(page, BacktestPage) and not page.job.running:
            page.refresh_versions()
        elif isinstance(page, GeneratorPage):
            selected = page.strategy_combo.currentData()
            page.strategy_combo.clear()
            for identifier, label in page.strategies.list_versions():
                page.strategy_combo.addItem(label, identifier)
            page.strategy_combo.setCurrentIndex(max(0, page.strategy_combo.findData(selected)))
        self.page_stack.setCurrentIndex(index)
        button = self.navigation.button(index)
        if button is not None:
            button.setChecked(True)

    def open_picker(self, code: GameCode) -> None:
        self.show_page(1)
        page = self.page_stack.widget(1)
        if isinstance(page, GeneratorPage):
            page.game_combo.setCurrentIndex(page.game_combo.findData(code))
            page.game_combo.setFocus()

    def start_results_sync(self) -> None:
        if self.results_sync is not None:
            self.results_sync.start()

    def _show_sync_status(self, message: str) -> None:
        self.statusBar().showMessage(message)
        if self.draw_history_page is not None:
            self.draw_history_page.set_sync_status(message)

    def closeEvent(self, event: QCloseEvent) -> None:
        active = [job for job in self.findChildren(JobController) if job.running]
        if active:
            for job in active:
                job.cancel()
            self.statusBar().showMessage("Waiting for background work to finish; close again when ready.")
            event.ignore()
            return
        if self.results_sync is not None:
            self.results_sync.shutdown()
        super().closeEvent(event)
