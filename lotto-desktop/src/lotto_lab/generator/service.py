from __future__ import annotations

from datetime import date, timedelta

from lotto_lab.analytics.service import AnalyticsService
from lotto_lab.domain import GameCode
from lotto_lab.generator.engine import WeightedGenerator
from lotto_lab.generator.models import GeneratedCombination
from lotto_lab.generator.repository import TicketRepository
from lotto_lab.strategy.repository import StrategyRepository


class GeneratorService:
    def __init__(
        self,
        analytics: AnalyticsService,
        strategies: StrategyRepository,
        tickets: TicketRepository,
        engine: WeightedGenerator | None = None,
    ) -> None:
        self.analytics = analytics
        self.strategies = strategies
        self.tickets = tickets
        self.engine = engine or WeightedGenerator()

    def generate(
        self,
        *,
        game_code: GameCode | str,
        strategy_version_id: int,
        window: int,
        ticket_count: int,
        cutoff: date | None = None,
    ) -> tuple[GeneratedCombination, ...]:
        if not 1 <= ticket_count <= 100:
            raise ValueError("Number of tickets must be between 1 and 100")
        game_code = GameCode(game_code)
        effective_cutoff = cutoff or (date.today() + timedelta(days=1))
        label, config = self.strategies.acquire_config(strategy_version_id)
        snapshot = self.analytics.snapshot(game_code, window=window, cutoff=effective_cutoff)
        combinations = tuple(
            self.engine.generate(snapshot=snapshot, config=config, strategy_label=label)
            for _ in range(ticket_count)
        )
        for combination in combinations:
            self.tickets.save(
                combination,
                game_code=game_code,
                strategy_version_id=strategy_version_id,
                historical_cutoff=effective_cutoff,
            )
        return combinations
