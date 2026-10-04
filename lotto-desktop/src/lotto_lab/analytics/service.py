"""Build analytics snapshots from a look-ahead-safe repository query."""

from __future__ import annotations

from datetime import date, timedelta

from lotto_lab.analytics.engine import AnalyticsEngine, AnalyticsSnapshot
from lotto_lab.domain import GameCode, SUPPORTED_GAMES, game_definition
from lotto_lab.draw_history.repository import DrawRepository


class AnalyticsService:
    def __init__(self, repository: DrawRepository, engine: AnalyticsEngine | None = None) -> None:
        self.repository = repository
        self.engine = engine or AnalyticsEngine()

    def snapshot(
        self,
        game_code: GameCode | str,
        *,
        window: int = 100,
        cutoff: date | None = None,
    ) -> AnalyticsSnapshot:
        if window <= 0:
            raise ValueError("Historical window must be positive")
        game_code = GameCode(game_code)
        effective_cutoff = cutoff or (date.today() + timedelta(days=1))
        selected_desc = self.repository.list_draws(
            game_code=game_code, before=effective_cutoff, limit=window, newest_first=True
        )
        selected = tuple(reversed(selected_desc))
        cross: list = []
        for game in SUPPORTED_GAMES:
            recent = self.repository.list_draws(
                game_code=game.code, before=effective_cutoff, limit=window, newest_first=True
            )
            cross.extend(recent)
        return self.engine.analyze(
            game_code=game_code,
            maximum_number=game_definition(game_code).maximum_number,
            game_draws=selected,
            cross_game_draws=tuple(cross),
        )
