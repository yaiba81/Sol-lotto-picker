"""Chronological simulations with bounded memory and explicit point-in-time inputs."""
from dataclasses import dataclass, field
from collections import Counter
from datetime import date
from random import Random
from threading import Event
from typing import Callable, Protocol
from lotto_lab.analytics.engine import AnalyticsSnapshot
from lotto_lab.domain import HistoricalDraw
from lotto_lab.strategy.config import StrategyConfig

from lotto_lab.domain import GameCode
from lotto_lab.generator.engine import WeightedGenerator
from lotto_lab.analytics.range_analyzer import range_pattern, pattern_label


@dataclass(frozen=True)
class BacktestRequest:
    game_code: GameCode
    first_date: date
    last_date: date
    strategy_ids: tuple[int, ...]
    tickets_per_draw: int = 100
    window: int = 100
    seed: int = 42

    def __post_init__(self):
        object.__setattr__(self, "game_code", GameCode(self.game_code))
        if self.first_date > self.last_date or self.last_date > date.today():
            raise ValueError("Choose a valid historical date interval")
        if any(type(value) is not int for value in (self.tickets_per_draw, self.window, *self.strategy_ids)):
            raise ValueError("Workload, window, and strategy identifiers must be integers")
        if not self.strategy_ids or len(set(self.strategy_ids)) != len(self.strategy_ids):
            raise ValueError("Select distinct strategy versions")
        if not 1 <= self.tickets_per_draw <= 10000 or not 1 <= self.window <= 10000:
            raise ValueError("Tickets and historical window must be between 1 and 10000")
        if type(self.seed) is not int or not 0 <= self.seed <= 2**63 - 1:
            raise ValueError("Seed must be an integer between 0 and 2^63 - 1")


@dataclass(frozen=True)
class StrategyResult:
    version_id: int
    label: str
    counts: tuple[int, ...]
    mean: float
    variance: float
    range_patterns: dict[str, int] = field(default_factory=dict)

    @classmethod
    def from_counts(cls, identifier, label, counts, range_patterns=None):
        total = sum(counts)
        mean = sum(i * count for i, count in enumerate(counts)) / total if total else 0.0
        variance = sum(count * (i - mean)**2 for i, count in enumerate(counts)) / total if total else 0.0
        return cls(identifier, label, tuple(counts), mean, variance, dict(range_patterns or {}))


@dataclass(frozen=True)
class BacktestReport:
    run_id: int
    status: str
    results: tuple[StrategyResult, ...]


class DrawSource(Protocol):
    def list_draws(self, *, game_code: GameCode) -> tuple[HistoricalDraw, ...]: ...


class SnapshotSource(Protocol):
    def snapshot(self, game_code: GameCode, *, window: int, cutoff: date) -> AnalyticsSnapshot: ...


class RunStore(Protocol):
    def start(self, request: BacktestRequest) -> tuple[int, tuple[tuple[int, str, StrategyConfig], ...]]: ...
    def finish(self, run_id: int, status: str, results: tuple[StrategyResult, ...]) -> None: ...


class BacktestService:
    def __init__(self, draws: DrawSource, analytics: SnapshotSource, repository: RunStore) -> None:
        self.draws = draws
        self.analytics = analytics
        self.repository = repository

    def run(self, request: BacktestRequest, cancel: Event | None = None,
            progress: Callable[[int, int], None] = lambda done, total: None) -> BacktestReport:
        cancel = cancel or Event()
        targets = tuple(draw for draw in self.draws.list_draws(game_code=request.game_code)
                        if request.first_date <= draw.draw_date <= request.last_date)
        targets = tuple(sorted(targets, key=lambda draw: draw.draw_date))
        if not targets:
            raise ValueError("No stored draws in this interval. Import history or change the dates.")
        run_id, versions = self.repository.start(request)
        counts = {identifier: [0] * 7 for identifier in request.strategy_ids}
        patterns = {identifier: Counter() for identifier in request.strategy_ids}
        # Separate equal-seeded streams make each version independent of selection order.
        engines = {identifier: WeightedGenerator(Random(request.seed)) for identifier in request.strategy_ids}
        total = len(targets) * len(versions) * request.tickets_per_draw
        done = 0
        status = "completed"
        try:
            progress(0, total)
            for target in targets:
                if cancel.is_set():
                    status = "cancelled"
                    break
                snapshot = self.analytics.snapshot(request.game_code, window=request.window, cutoff=target.draw_date)
                winning = set(target.numbers)
                for identifier, label, config in versions:
                    for _ in range(request.tickets_per_draw):
                        if cancel.is_set():
                            status = "cancelled"
                            break
                        ticket = engines[identifier].generate(snapshot=snapshot, config=config, strategy_label=label)
                        counts[identifier][len(winning.intersection(ticket.numbers))] += 1
                        patterns[identifier][pattern_label(range_pattern(ticket.numbers, snapshot.maximum_number))] += 1
                        done += 1
                        if done % 25 == 0 or done == total:
                            progress(done, total)
                    if status == "cancelled":
                        break
                if status == "cancelled":
                    break
            results = tuple(StrategyResult.from_counts(identifier, label, counts[identifier], patterns[identifier])
                            for identifier, label, _ in versions)
            self.repository.finish(run_id, status, results)
            progress(done, total)
            return BacktestReport(run_id, status, results)
        except Exception:
            results = tuple(StrategyResult.from_counts(identifier, label, counts[identifier], patterns[identifier])
                            for identifier, label, _ in versions)
            self.repository.finish(run_id, "failed", results)
            raise
