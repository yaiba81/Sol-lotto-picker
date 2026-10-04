"""Presentation of range statistics calculated by the analytics worker."""
from PySide6.QtWidgets import QWidget, QVBoxLayout, QLabel, QTabWidget, QTableWidget, QComboBox, QScrollArea

from lotto_lab.analytics.range_analyzer import pattern_label, uniform_patterns
from lotto_lab.ui.charts import HistoryChart
from lotto_lab.ui.paged_table import PagedTable


def percent(value):
    return "No observations" if value is None else f"{100 * value:.2f}%"


class RangeAnalysisPanel(QScrollArea):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWidgetResizable(True)
        content = QWidget()
        self.setWidget(content)
        layout = QVBoxLayout(content)
        self.context = QLabel("Refresh analysis to load range statistics.")
        self.context.setWordWrap(True)
        layout.addWidget(self.context)
        self.tabs = QTabWidget()
        self.tabs.setMinimumHeight(360)
        layout.addWidget(self.tabs)
        self.frequency_table, self.frequency = self.add_table("Range frequency", (
            "Range", "Valid values", "Selections", "Draws present", "Observed presence",
            "Expected presence", "Deviation (pp)", "Average / draw", "Expected average"))
        pattern_panel = QWidget()
        pattern_layout = QVBoxLayout(pattern_panel)
        self.order = QComboBox()
        self.order.addItems(("Most frequent observed patterns", "Least frequent observed patterns", "All valid patterns (including unseen)"))
        self.order.setAccessibleName("Range pattern ordering")
        self.order.setMinimumContentsLength(20)
        self.order.setSizeAdjustPolicy(QComboBox.SizeAdjustPolicy.AdjustToMinimumContentsLengthWithIcon)
        pattern_layout.addWidget(self.order)
        self.pattern_table = QTableWidget(0, 4)
        self.pattern_table.setHorizontalHeaderLabels(("Pattern", "Draws", "Observed frequency", "Expected frequency"))
        self.pattern_table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        self.patterns = PagedTable(self.pattern_table)
        pattern_layout.addWidget(self.patterns)
        self.tabs.addTab(pattern_panel, "Patterns")
        self.high_table, self.high = self.add_table("40+ / 50+", ("Range", "Metric", "Draws", "Observed", "Expected random", "Deviation"))
        self.chart = HistoryChart()
        self.tabs.addTab(self.chart, "Range chart")
        self.statistics = None
        self.order.currentIndexChanged.connect(self.render_patterns)

    def add_table(self, title, headers):
        table = QTableWidget(0, len(headers))
        table.setHorizontalHeaderLabels(headers)
        table.setEditTriggers(QTableWidget.EditTrigger.NoEditTriggers)
        table.setAccessibleName(title)
        paged = PagedTable(table)
        self.tabs.addTab(paged, title)
        return table, paged

    def show_snapshot(self, snapshot, window):
        stats = snapshot.range_statistics
        if stats is None:
            return
        self.statistics = stats
        labels = [row.label for row in stats.ranges]
        self.context.setText(
            f"Game {snapshot.game_code.value} | Historical window: latest {window} draws | "
            f"Loaded: {stats.draw_count}. Pattern order: {', '.join(labels)}.\n"
            "Presence = at least one per draw; pp = percentage points. Historical deviations are not future odds.")
        self.frequency.set_rows(tuple((row.label, row.size, row.selections, row.draws_present,
            percent(row.observed_presence), percent(row.expected_presence),
            "—" if row.observed_presence is None else f"{100 * (row.observed_presence - row.expected_presence):+.2f}",
            "No observations" if row.observed_average is None else f"{row.observed_average:.3f}",
            f"{row.expected_average:.3f}") for row in stats.ranges))
        self.frequency_table.resizeColumnsToContents()
        self.render_patterns()
        rows = []
        for high in stats.high_numbers:
            for count, expected in enumerate(high.expected_counts):
                observed = high.counts[count] / stats.draw_count if stats.draw_count else None
                rows.append((f"{high.threshold}+", f"Exactly {count}", high.counts[count], percent(observed),
                    percent(expected), "—" if observed is None else f"{100 * (observed - expected):+.2f} pp"))
            for minimum, observed in ((1, high.at_least_one), (2, high.at_least_two)):
                expected = sum(high.expected_counts[minimum:])
                rows.append((f"{high.threshold}+", f"At least {minimum}", sum(high.counts[minimum:]),
                    percent(observed), percent(expected), "—" if observed is None else f"{100 * (observed - expected):+.2f} pp"))
            rows.append((f"{high.threshold}+", "Average count / draw", "—",
                "No observations" if high.average is None else f"{high.average:.3f}",
                f"{high.expected_average:.3f}", "—" if high.average is None else f"{high.average - high.expected_average:+.3f}"))
        self.high.set_rows(rows)
        self.high_table.resizeColumnsToContents()
        self.chart.range_comparison(stats)

    def render_patterns(self):
        stats = self.statistics
        if stats is None:
            return
        expected = dict(uniform_patterns(stats.game_max))
        counts = {p: stats.patterns.get(p, 0) for p in expected} if self.order.currentIndex() == 2 else stats.patterns
        ordered = sorted(counts, key=lambda p: ((-counts[p] if self.order.currentIndex() == 0 else counts[p]), p))
        self.patterns.set_rows(tuple((pattern_label(p), counts[p],
            percent(counts[p] / stats.draw_count if stats.draw_count else None), percent(expected[p])) for p in ordered))
        self.pattern_table.resizeColumnsToContents()
