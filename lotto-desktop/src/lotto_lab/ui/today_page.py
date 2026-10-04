"""Today's Manila-time draw schedule."""

from __future__ import annotations

from datetime import datetime

from PySide6.QtCore import Qt, QTimer, Signal
from PySide6.QtWidgets import QFrame, QHBoxLayout, QLabel, QPushButton, QScrollArea, QVBoxLayout, QWidget

from lotto_lab.domain import GameCode
from lotto_lab.schedule import MANILA, ScheduleService


class TodayPage(QWidget):
    pick_requested = Signal(object)
    results_requested = Signal()

    def __init__(self, schedule: ScheduleService, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("dashboard")
        self.schedule = schedule
        outer = QVBoxLayout(self)
        outer.setContentsMargins(32, 28, 32, 28)
        heading = QLabel("Today's Lotto")
        heading.setObjectName("pageTitle")
        outer.addWidget(heading)
        self.date_label = QLabel()
        self.date_label.setObjectName("pageDescription")
        outer.addWidget(self.date_label)
        self.notice = QLabel("Regular PCSO schedule · Asia/Manila. Check PCSO for special draw changes.")
        self.notice.setObjectName("notice")
        self.notice.setWordWrap(True)
        outer.addWidget(self.notice)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.content = QWidget()
        self.cards = QVBoxLayout(self.content)
        self.cards.setAlignment(Qt.AlignmentFlag.AlignTop)
        scroll.setWidget(self.content)
        outer.addWidget(scroll, 1)
        self.timer = QTimer(self)
        self.timer.setInterval(60_000)
        self.timer.timeout.connect(self.refresh)
        self.timer.start()
        self.refresh()

    def refresh(self, now: datetime | None = None) -> None:
        current = now.astimezone(MANILA) if now is not None else datetime.now(MANILA)
        self.date_label.setText(current.strftime("%A, %B %d, %Y") + " · Philippine time")
        while self.cards.count():
            item = self.cards.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        draws = self.schedule.today(current)
        section = QLabel("Scheduled Draws" if draws else "No lotto draws scheduled today.")
        section.setObjectName("eyebrow")
        self.cards.addWidget(section)
        for draw in draws:
            self._add_card(draw.game.code, draw.game.name, draw.at.strftime("%I:%M %p").lstrip("0"),
                           "Draw completed" if draw.status == "DRAW_COMPLETED" else "Draw today",
                           completed=draw.status == "DRAW_COMPLETED")
        next_draw = self.schedule.next_draw(current)
        if next_draw is not None:
            title = QLabel("Next Draw")
            title.setObjectName("eyebrow")
            self.cards.addWidget(title)
            day = "Today" if next_draw.at.date() == current.date() else next_draw.at.strftime("%A, %B %d")
            self._add_card(next_draw.game.code, next_draw.game.name,
                           f"{day} · {next_draw.at.strftime('%I:%M %p').lstrip('0')}", "Upcoming")
        self.cards.addStretch()

    def _add_card(self, code: GameCode, name: str, when: str, status: str, *, completed: bool = False) -> None:
        card = QFrame()
        card.setObjectName("controlPanel")
        layout = QVBoxLayout(card)
        top = QHBoxLayout()
        game = QLabel(name)
        game.setObjectName("scheduleGame")
        top.addWidget(game)
        top.addStretch()
        state = QLabel(status)
        state.setObjectName("scheduleStatus")
        top.addWidget(state)
        layout.addLayout(top)
        layout.addWidget(QLabel(when))
        buttons = QHBoxLayout()
        pick = QPushButton("Pick Numbers")
        pick.setObjectName("primaryButton")
        pick.setAccessibleName(f"Pick numbers for {name}")
        pick.clicked.connect(lambda checked=False, selected=code: self.pick_requested.emit(selected))
        buttons.addWidget(pick)
        if completed:
            results = QPushButton("View Results")
            results.setAccessibleName(f"View stored results for {name}")
            results.clicked.connect(self.results_requested.emit)
            buttons.addWidget(results)
        buttons.addStretch()
        layout.addLayout(buttons)
        self.cards.addWidget(card)
