"""Shared table paging for computed rows and bounded repository queries."""
from collections.abc import Callable, Sequence

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QComboBox, QHBoxLayout, QLabel, QPushButton, QSpinBox,
    QTableWidget, QTableWidgetItem, QVBoxLayout, QWidget,
)

Row = Sequence[object]
PageLoader = Callable[[int, int], Sequence[Row]]


class PagedTable(QWidget):
    """Keep only the current page in Qt; loaders receive offset and page size."""

    def __init__(self, table: QTableWidget, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.table = table
        self.total = 0
        self._load: PageLoader = lambda offset, limit: ()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(table, 1)
        self.summary = QLabel("No rows")
        self.summary.setObjectName("statusMessage")
        layout.addWidget(self.summary)
        controls = QHBoxLayout()
        self.previous = QPushButton("Previous")
        self.next = QPushButton("Next")
        self.page = QSpinBox()
        self.page.setRange(1, 1)
        self.page.setKeyboardTracking(False)
        self.page.setAccessibleName("Table page number")
        self.page_count = QLabel("of 1")
        self.page_size = QComboBox()
        self.page_size.setAccessibleName("Rows per page")
        for size in (10, 25, 50, 100):
            self.page_size.addItem(str(size), size)
        self.page_size.setCurrentIndex(1)
        for button in (self.previous, self.next):
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setAccessibleName(f"{button.text()} table page")
        page_label = QLabel("Page")
        page_label.setBuddy(self.page)
        size_label = QLabel("Rows")
        size_label.setBuddy(self.page_size)
        for widget in (self.previous, page_label, self.page, self.page_count, self.next):
            controls.addWidget(widget)
        controls.addStretch()
        controls.addWidget(size_label)
        controls.addWidget(self.page_size)
        layout.addLayout(controls)
        self.previous.clicked.connect(lambda: self.page.setValue(self.page.value() - 1))
        self.next.clicked.connect(lambda: self.page.setValue(self.page.value() + 1))
        self.page.valueChanged.connect(self._render)
        self.page_size.currentIndexChanged.connect(self._reset)
        self._reset()

    def set_rows(self, rows: Sequence[Row]) -> None:
        """Computed results are already in memory; paging does not affect charts."""
        stored = tuple(tuple(row) for row in rows)
        self.set_source(len(stored), lambda offset, limit: stored[offset:offset + limit])

    def set_source(self, total: int, loader: PageLoader) -> None:
        if total < 0:
            raise ValueError("Row count cannot be negative")
        self.total = total
        self._load = loader
        self._reset()

    def _reset(self) -> None:
        size = self.page_size.currentData()
        pages = max(1, (self.total + size - 1) // size)
        self.page.blockSignals(True)
        self.page.setRange(1, pages)
        self.page.setValue(1)
        self.page.blockSignals(False)
        self.page_count.setText(f"of {pages}")
        self._render()

    def _render(self) -> None:
        size = self.page_size.currentData()
        offset = (self.page.value() - 1) * size
        rows = self._load(offset, size) if self.total else ()
        self.table.clearContents()
        self.table.setRowCount(len(rows))
        for row, values in enumerate(rows):
            self.table.setVerticalHeaderItem(row, QTableWidgetItem(str(offset + row + 1)))
            for column, value in enumerate(values):
                self.table.setItem(row, column, QTableWidgetItem(str(value)))
        self.table.resizeColumnsToContents()
        self.table.scrollToTop()
        self.previous.setEnabled(self.page.value() > 1)
        self.next.setEnabled(self.page.value() < self.page.maximum())
        self.page.setEnabled(self.total > 0)
        self.summary.setText(
            f"Rows {offset + 1}-{offset + len(rows)} of {self.total}"
            if rows else "No rows"
        )
