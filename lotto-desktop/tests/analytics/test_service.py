from datetime import date

from lotto_lab.analytics.service import AnalyticsService
from lotto_lab.domain import GameCode, HistoricalDraw
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.persistence.bootstrap import seed_supported_games
from lotto_lab.persistence.database import Database


def test_snapshot_cannot_observe_target_or_future_draws(tmp_path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'analytics.sqlite3').as_posix()}")
    database.create_schema()
    seed_supported_games(database)
    repository = DrawRepository(database)
    repository.add_many(
        (
            HistoricalDraw(GameCode.LOTTO_6_42, date(2025, 1, 1), (1, 2, 3, 4, 5, 6)),
            HistoricalDraw(GameCode.LOTTO_6_42, date(2025, 1, 2), (37, 38, 39, 40, 41, 42)),
        )
    )

    snapshot = AnalyticsService(repository).snapshot(
        GameCode.LOTTO_6_42, cutoff=date(2025, 1, 2), window=100
    )

    assert snapshot.draw_count == 1
    assert snapshot.number_frequencies[1] == 1
    assert snapshot.number_frequencies[42] == 0
    database.dispose()

