"""Local PCSO draw schedule and Manila-time queries."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from lotto_lab.domain import GameCode, game_definition

MANILA = ZoneInfo("Asia/Manila")
SOURCE_URL = "https://www.pcso.gov.ph/pcsofiles/transparency/02/Annual%20Report%202021%282%29.pdf"


@dataclass(frozen=True, slots=True)
class ScheduledGame:
    code: GameCode
    draw_days: tuple[int, ...]  # Monday = 0
    draw_time: time
    active: bool = True
    description: str = ""
    source_url: str = SOURCE_URL

    @property
    def name(self) -> str:
        return game_definition(self.code).name

    @property
    def maximum_number(self) -> int:
        return game_definition(self.code).maximum_number

    @property
    def numbers_required(self) -> int:
        return game_definition(self.code).picks


@dataclass(frozen=True, slots=True)
class ScheduledDraw:
    game: ScheduledGame
    at: datetime
    status: str


# PCSO's published regular 9 PM schedule. Local overrides can reflect temporary changes.
DEFAULT_GAMES = (
    ScheduledGame(GameCode.LOTTO_6_42, (1, 3, 5), time(21)),
    ScheduledGame(GameCode.MEGA_LOTTO_6_45, (0, 2, 4), time(21)),
    ScheduledGame(GameCode.SUPER_LOTTO_6_49, (1, 3, 6), time(21)),
    ScheduledGame(GameCode.GRAND_LOTTO_6_55, (0, 2, 5), time(21)),
    ScheduledGame(GameCode.ULTRA_LOTTO_6_58, (1, 4, 6), time(21)),
)


class ScheduleService:
    def __init__(self, games: tuple[ScheduledGame, ...] = DEFAULT_GAMES) -> None:
        self.games = games

    @classmethod
    def from_json(cls, path: Path) -> "ScheduleService":
        """Load an optional local override; the file contains a `games` array."""
        if not path.exists():
            return cls()
        data = json.loads(path.read_text(encoding="utf-8"))
        games = tuple(ScheduledGame(
            code=GameCode(item["id"]),
            draw_days=tuple(int(day) for day in item["drawDays"]),
            draw_time=time.fromisoformat(item["drawTime"]),
            active=bool(item.get("active", True)),
            description=str(item.get("description", "")),
            source_url=str(item.get("sourceUrl", SOURCE_URL)),
        ) for item in data["games"])
        if len({game.code for game in games}) != len(games):
            raise ValueError("Duplicate schedule game ID")
        if any(not game.draw_days or any(day not in range(7) for day in game.draw_days) for game in games):
            raise ValueError("Draw days must use Monday=0 through Sunday=6")
        return cls(games)

    def today(self, now: datetime | None = None) -> tuple[ScheduledDraw, ...]:
        current = self._manila_now(now)
        draws = (self._draw(game, current.date(), current) for game in self.games
                 if game.active and current.weekday() in game.draw_days)
        return tuple(sorted(draws, key=lambda draw: (draw.at, draw.game.name)))

    def next_draw(self, now: datetime | None = None) -> ScheduledDraw | None:
        current = self._manila_now(now)
        upcoming = (self._draw(game, current.date() + timedelta(days=offset), current)
                    for game in self.games if game.active for offset in range(8)
                    if (current.date() + timedelta(days=offset)).weekday() in game.draw_days)
        return min((draw for draw in upcoming if draw.at > current),
                   key=lambda draw: (draw.at, draw.game.name), default=None)

    @staticmethod
    def _manila_now(now: datetime | None) -> datetime:
        if now is None:
            return datetime.now(MANILA)
        if now.tzinfo is None:
            raise ValueError("Current time must include a timezone")
        return now.astimezone(MANILA)

    @staticmethod
    def _draw(game: ScheduledGame, day: date, current: datetime) -> ScheduledDraw:
        at = datetime.combine(day, game.draw_time, MANILA)
        return ScheduledDraw(game, at, "UPCOMING" if current < at else "DRAW_COMPLETED")
