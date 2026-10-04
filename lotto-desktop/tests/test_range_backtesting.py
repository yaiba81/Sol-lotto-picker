from dataclasses import replace
from datetime import date

import pytest
from sqlalchemy import delete

from lotto_lab.analytics.service import AnalyticsService
from lotto_lab.backtesting.repository import BacktestRepository
from lotto_lab.backtesting.service import BacktestRequest, BacktestService
from lotto_lab.domain import GameCode, HistoricalDraw
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.persistence.models import StrategyVersion, BacktestRangePattern
from lotto_lab.strategy.config import JONATHAN_RANGE_CONFIG
from lotto_lab.strategy.repository import StrategyRepository


def test_range_reference_seeding_preserves_used_versions_and_existing_v2(db):
    repository = StrategyRepository(db)
    enhanced = next(i for i, _ in repository.list_versions() if repository.get_config(i)[1] == JONATHAN_RANGE_CONFIG)
    with db.session() as session:
        session.delete(session.get(StrategyVersion, enhanced))
    original = next(i for i, label in repository.list_versions() if label == "Jonathan Weighted v1")
    clone = repository.clone(original)
    repository.acquire_config(clone)
    before = repository.get_config(clone)
    repository.seed_built_ins()
    repository.seed_built_ins()
    assert repository.get_config(clone) == before
    enhanced = [(i, label) for i, label in repository.list_versions() if repository.get_config(i)[1] == JONATHAN_RANGE_CONFIG]
    assert len(enhanced) == 1 and enhanced[0][1] == "Jonathan Weighted v3"
    with pytest.raises(ValueError):
        repository.save_config(enhanced[0][0], replace(JONATHAN_RANGE_CONFIG, range_strength=0.5))


def test_range_backtest_uses_only_prior_window_and_persists_patterns(db):
    game = GameCode.ULTRA_LOTTO_6_58
    draws = DrawRepository(db)
    draws.add_many(tuple(HistoricalDraw(game, date(2025,1,day), values) for day, values in (
        (1, (1,2,3,4,5,6)), (2, (10,20,30,40,50,58)), (3, (50,51,52,53,54,55)))))
    strategies = StrategyRepository(db)
    ids = tuple(i for i, label in strategies.list_versions()
        if label in ("Pure Random v1", "Jonathan Weighted v1", "Jonathan Weighted v2"))
    assert len(ids) == 3
    actual = AnalyticsService(draws)
    seen = []
    class CheckedAnalytics:
        def snapshot(self, code, *, window, cutoff):
            snapshot = actual.snapshot(code, window=window, cutoff=cutoff)
            expected = {(6,0,0,0,0,0): 1} if cutoff == date(2025,1,2) else {(0,1,1,1,1,2): 1}
            assert snapshot.range_statistics.patterns == expected
            assert snapshot.range_statistics.draw_count == 1
            seen.append(cutoff)
            return snapshot
    repository = BacktestRepository(db)
    request = BacktestRequest(game, date(2025,1,2), date(2025,1,3), ids, 12, 1, 87)
    service = BacktestService(draws, CheckedAnalytics(), repository)
    first = service.run(request)
    assert seen == [date(2025,1,2), date(2025,1,3)]
    assert all(sum(r.range_patterns.values()) == sum(r.counts) == 24 for r in first.results)
    assert repository.report(first.run_id) == first
    second = service.run(replace(request, strategy_ids=tuple(reversed(ids))))
    assert first.results == second.results
    # Same-date/future imports cannot alter this earlier target's training or tickets.
    earlier = service.run(replace(request, last_date=date(2025,1,2)))
    draws.add_many((HistoricalDraw(game, date(2025,2,1), (50,51,52,53,54,55)),))
    repeated = service.run(replace(request, last_date=date(2025,1,2)))
    assert earlier.results == repeated.results
    # Legacy reports remain readable without generated-pattern rows.
    with db.session() as session:
        session.execute(delete(BacktestRangePattern).where(BacktestRangePattern.run_id == first.run_id))
    assert all(not r.range_patterns for r in repository.report(first.run_id).results)


def test_partial_pattern_aggregates_survive_cancel_and_failure(db):
    from threading import Event
    game = GameCode.GRAND_LOTTO_6_55
    draws = DrawRepository(db)
    draws.add_many((HistoricalDraw(game, date(2025,1,1), (1,10,20,30,40,55)),))
    strategies = StrategyRepository(db)
    ids = tuple(i for i, _ in strategies.list_versions() if strategies.get_config(i)[1] == JONATHAN_RANGE_CONFIG)
    repository = BacktestRepository(db)
    request = BacktestRequest(game, date(2025,1,1), date(2025,1,1), ids, 100)
    event = Event()
    def cancel(done, total):
        if done == 25:
            event.set()
    service = BacktestService(draws, AnalyticsService(draws), repository)
    report = service.run(request, event, cancel)
    assert report.status == "cancelled"
    assert sum(report.results[0].range_patterns.values()) == 25
    assert repository.report(report.run_id) == report
    def fail(done, total):
        if done == 25:
            raise RuntimeError("Interrupted progress")
    with pytest.raises(RuntimeError):
        service.run(request, progress=fail)
    failed = repository.report(repository.list_runs()[0][0])
    assert failed.status == "failed"
    assert sum(failed.results[0].range_patterns.values()) == sum(failed.results[0].counts) == 25
