"""Matplotlib Qt canvases; all chart rendering stays on the GUI thread."""
from PySide6.QtWidgets import QWidget, QVBoxLayout
from matplotlib.figure import Figure
from matplotlib.backends.backend_qtagg import FigureCanvasQTAgg, NavigationToolbar2QT


class HistoryChart(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        self.figure = Figure(figsize=(7, 4), layout="constrained", facecolor="#F8FAFC")
        self.canvas = FigureCanvasQTAgg(self.figure)
        self.canvas.setAccessibleName("Historical chart; equivalent values are available in the data table")
        layout.addWidget(NavigationToolbar2QT(self.canvas, self))
        layout.addWidget(self.canvas)

    def bars(self, title, labels, values, xlabel, ylabel):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        ax.bar([str(label) for label in labels], values, color="#0369A1")
        ax.set(title=title, xlabel=xlabel, ylabel=ylabel)
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
        if len(labels) > 20:
            ax.tick_params(axis="x", labelsize=8, rotation=90)
        if not any(values):
            ax.text(0.5, 0.5, "No observations in this window", transform=ax.transAxes, ha="center")
        self.canvas.draw_idle()

    def range_comparison(self, statistics):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        positions = list(range(len(statistics.ranges)))
        if statistics.draw_count:
            ax.bar([x - 0.2 for x in positions], [r.observed_average for r in statistics.ranges],
                width=0.4, label="Observed average", color="#0369A1")
        else:
            ax.text(0.5, 0.9, "No observations in this window", transform=ax.transAxes, ha="center")
        ax.bar([x + 0.2 for x in positions], [r.expected_average for r in statistics.ranges],
            width=0.4, label="Uniform random expectation", fill=False, hatch="///", edgecolor="#0369A1")
        ax.set_xticks(positions, [r.label for r in statistics.ranges])
        ax.set(title="Range distribution", xlabel="Number range", ylabel="Average selections per draw")
        ax.legend()
        ax.grid(axis="y", alpha=0.2)
        ax.set_axisbelow(True)
        self.canvas.draw_idle()

    def comparison(self, results):
        self.figure.clear()
        ax = self.figure.add_subplot(111)
        markers = ("o", "s", "^", "D", "v", "x")
        for index, result in enumerate(results):
            total = sum(result.counts)
            ax.plot(range(7), [100 * n / total if total else 0 for n in result.counts],
                    marker=markers[index % len(markers)], label=result.label)
        ax.set(title="Observed match distribution", xlabel="Matching numbers", ylabel="Tickets (%)")
        ax.set_xticks(range(7))
        ax.grid(alpha=0.2)
        if results:
            ax.legend(fontsize=8)
        self.canvas.draw_idle()
