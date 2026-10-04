"""Transactional run lifecycle using normalized aggregate result rows."""
from sqlalchemy import select, text, delete
from lotto_lab.persistence.models import (BacktestRun, BacktestResult, Game,
    StrategyVersion, BacktestSettings, BacktestRangePattern, utc_now)
from lotto_lab.strategy.config import StrategyConfig
from lotto_lab.backtesting.service import BacktestReport, BacktestRequest, StrategyResult
from lotto_lab.persistence.database import Database


class BacktestRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def start(self, request: BacktestRequest) -> tuple[int, tuple[tuple[int, str, StrategyConfig], ...]]:
        with self.database.session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            versions = []
            for identifier in sorted(request.strategy_ids):
                version = session.get(StrategyVersion, identifier)
                if version is None:
                    raise LookupError("Strategy version does not exist")
                parameter = next(p for p in version.parameters if p.key == "config")
                config = StrategyConfig.from_json(parameter.value_json)
                version.is_locked = True
                versions.append((identifier, version.label, config))
            game = session.scalar(select(Game).where(Game.code == request.game_code.value))
            run = BacktestRun(name=f"Historical comparison (window {request.window})", game_id=game.id,
                first_draw_date=request.first_date, last_draw_date=request.last_date,
                tickets_per_draw=request.tickets_per_draw, random_seed=str(request.seed), status="running")
            session.add(run)
            session.flush()
            # The scalar window is normalized separately so rerun settings are retained.
            session.add(BacktestSettings(run_id=run.id, historical_window=request.window))
            for identifier, _, _ in versions:
                for matches in range(7):
                    session.add(BacktestResult(backtest_run_id=run.id, strategy_version_id=identifier,
                        match_count=matches, occurrences=0, average_matches=0, variance=0))
            return run.id, tuple(versions)

    def finish(self, run_id: int, status: str, results: tuple[StrategyResult, ...]) -> None:
        with self.database.session() as session:
            run = session.get(BacktestRun, run_id)
            run.status = status
            run.completed_at = utc_now()
            by_id = {result.version_id: result for result in results}
            session.execute(delete(BacktestRangePattern).where(BacktestRangePattern.run_id == run_id))
            for result in results:
                session.add_all(BacktestRangePattern(run_id=run_id, strategy_version_id=result.version_id,
                    pattern=pattern, occurrences=count) for pattern, count in result.range_patterns.items())
            for row in run.results:
                result = by_id[row.strategy_version_id]
                row.occurrences = result.counts[row.match_count]
                row.average_matches = result.mean
                row.variance = result.variance

    def list_runs(self):
        with self.database.session() as session:
            return tuple((r.id, f"#{r.id} | {r.first_draw_date} to {r.last_draw_date} | {r.status} | seed {r.random_seed}")
                         for r in session.scalars(select(BacktestRun).order_by(BacktestRun.id.desc())))

    def report(self, run_id: int) -> BacktestReport:
        with self.database.session() as session:
            run = session.get(BacktestRun, run_id)
            if run is None:
                raise LookupError("Run does not exist")
            grouped = {}
            patterns = {}
            for row in session.scalars(select(BacktestRangePattern).where(BacktestRangePattern.run_id == run_id)):
                patterns.setdefault(row.strategy_version_id, {})[row.pattern] = row.occurrences
            for row in run.results:
                grouped.setdefault(row.strategy_version_id, [0] * 7)[row.match_count] = row.occurrences
            results = tuple(StrategyResult.from_counts(identifier, session.get(StrategyVersion, identifier).label, counts, patterns.get(identifier))
                            for identifier, counts in sorted(grouped.items()))
            return BacktestReport(run.id, run.status, results)
