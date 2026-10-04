from __future__ import annotations

from dataclasses import dataclass

from PySide6.QtCore import Qt
from PySide6.QtWidgets import QLabel, QVBoxLayout, QWidget


@dataclass(frozen=True, slots=True)
class PageDefinition:
    key: str
    label: str
    title: str
    description: str


PAGE_DEFINITIONS: tuple[PageDefinition, ...] = (
    PageDefinition("dashboard", "Today's Lotto", "Today's Lotto", "Scheduled PCSO draws in Philippine time."),
    PageDefinition("generator", "Generator", "Ticket Generator", "Generate transparent weighted-random or pure-random tickets."),
    PageDefinition("draw_history", "Draw History", "Draw History", "Import, inspect, and validate official historical results."),
    PageDefinition("analytics", "Analytics", "Analytics", "Explore frequencies, groups, sequences, parity, and cross-game repetition."),
    PageDefinition("strategy_lab", "Strategy Lab", "Strategy Lab", "Clone and version explainable weighting configurations."),
    PageDefinition("backtesting", "Backtesting", "Backtesting", "Compare strategies with point-in-time historical simulations."),
    PageDefinition("settings", "Settings", "Settings", "Manage local storage and application preferences."),
)


class PhasePage(QWidget):
    def __init__(self, definition: PageDefinition, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName(definition.key)

        layout = QVBoxLayout(self)
        layout.setContentsMargins(40, 36, 40, 36)
        layout.setSpacing(10)

        eyebrow = QLabel("LOTTO LAB")
        eyebrow.setObjectName("eyebrow")
        title = QLabel(definition.title)
        title.setObjectName("pageTitle")
        description = QLabel(definition.description)
        description.setObjectName("pageDescription")
        description.setWordWrap(True)

        notice = QLabel(
            "Foundation ready. This workspace will be activated in its scheduled development phase."
        )
        notice.setObjectName("notice")
        notice.setWordWrap(True)
        notice.setMaximumWidth(680)
        notice.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)

        layout.addWidget(eyebrow)
        layout.addWidget(title)
        layout.addWidget(description)
        layout.addSpacing(18)
        layout.addWidget(notice)
        layout.addStretch()

