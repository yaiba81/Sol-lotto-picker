from datetime import date
from dataclasses import replace
from threading import Event
import pytest
from sqlalchemy import select
from lotto_lab.analytics.service import AnalyticsService
from lotto_lab.domain import GameCode, HistoricalDraw
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.strategy.repository import StrategyRepository
from lotto_lab.backtesting.service import BacktestRequest, BacktestService, StrategyResult
from lotto_lab.backtesting.repository import BacktestRepository
from lotto_lab.persistence.models import BacktestRun, BacktestSettings


def setup(db):
    draws = DrawRepository(db)
    draws.add_many(tuple(HistoricalDraw(GameCode.LOTTO_6_42, date(2025, 1, day), numbers)
        for day, numbers in ((1, (1,2,3,4,5,6)), (2, (31,32,33,34,35,36)), (3, (37,38,39,40,41,42)))))
    strategies = StrategyRepository(db)
    ids = tuple(identifier for identifier, label in strategies.list_versions() if label in ("Pure Random v1", "Hybrid v1"))
    request = BacktestRequest(GameCode.LOTTO_6_42, date(2025,1,2), date(2025,1,3), ids, 4, 1, 42)
    repository = BacktestRepository(db)
    return draws, request, repository


def test_repeatable_persisted_order_independent_and_immutable(db):
    draws, request, repository = setup(db)
    before = draws.list_draws()
    service = BacktestService(draws, AnalyticsService(draws), repository)
    first = service.run(request)
    second = service.run(replace(request, strategy_ids=tuple(reversed(request.strategy_ids))))
    assert {r.version_id:r for r in first.results} == {r.version_id:r for r in second.results}
    assert first.status == "completed"
    assert all(sum(r.counts) == 8 for r in first.results)
    assert repository.report(first.run_id) == first
    assert draws.list_draws() == before
    assert all(StrategyRepository(db).is_locked(i) for i in request.strategy_ids)
    with db.session() as session:
        assert session.get(BacktestSettings, first.run_id).historical_window == 1
        assert session.get(BacktestRun, first.run_id).random_seed == "42"


def test_every_target_excludes_same_date_and_future_cross_game_data(db):
    draws, request, repository = setup(db)
    draws.add_many((HistoricalDraw(GameCode.MEGA_LOTTO_6_45, date(2025,1,2), (40,41,42,43,44,45)),))
    actual = AnalyticsService(draws)
    seen = []
    class CheckedAnalytics:
        def snapshot(self, game, *, window, cutoff):
            result = actual.snapshot(game, window=window, cutoff=cutoff)
            seen.append(cutoff)
            if cutoff == date(2025,1,2):
                assert result.number_frequencies[31] == 0
                assert result.cross_game_occurrences.get(42, 0) == 0
            assert result.number_frequencies[42] == 0
            assert result.draw_count == 1
            return result
    BacktestService(draws, CheckedAnalytics(), repository).run(request)
    assert seen == [date(2025,1,2), date(2025,1,3)]


def test_cancellation_and_failure_saved(db):
    draws, request, repository = setup(db)
    event = Event()
    progress = []
    def update(done, total):
        progress.append((done,total))
        event.set()
    report = BacktestService(draws, AnalyticsService(draws), repository).run(request, event, update)
    assert report.status == "cancelled"
    assert sum(sum(r.counts) for r in report.results) == 0
    assert progress
    class BrokenAnalytics:
        def snapshot(self, *args, **kwargs):
            raise RuntimeError("test failure")
    with pytest.raises(RuntimeError):
        BacktestService(draws, BrokenAnalytics(), repository).run(request)
    with db.session() as session:
        run = session.scalar(select(BacktestRun).order_by(BacktestRun.id.desc()))
        assert run.status == "failed"
        assert run.completed_at is not None


def test_known_aggregate_statistics():
    result = StrategyResult.from_counts(1, "Control v1", [1,2,1,0,0,0,0])
    assert result.mean == 1
    assert result.variance == 0.5


@pytest.mark.parametrize("change", [{"tickets_per_draw": 1.5}, {"window": True},
    {"strategy_ids": ()}, {"seed": -1}, {"first_date": date(2025,2,1)}])
def test_invalid_requests(db, change):
    _, request, _ = setup(db)
    with pytest.raises(ValueError):
        replace(request, **change)
