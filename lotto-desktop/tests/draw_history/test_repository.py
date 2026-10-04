from datetime import date

from lotto_lab.domain import GameCode, HistoricalDraw
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.persistence.bootstrap import seed_supported_games
from lotto_lab.persistence.database import Database


def test_repository_skips_existing_draw_and_enforces_strict_cutoff(tmp_path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'history.sqlite3').as_posix()}")
    database.create_schema()
    seed_supported_games(database)
    repository = DrawRepository(database)
    draws = (
        HistoricalDraw(GameCode.LOTTO_6_42, date(2026, 1, 1), (1, 2, 3, 4, 5, 6)),
        HistoricalDraw(GameCode.LOTTO_6_42, date(2026, 1, 2), (7, 8, 9, 10, 11, 12)),
    )

    assert repository.add_many(draws) == 2
    assert repository.add_many(draws) == 0
    before_target = repository.list_draws(
        game_code=GameCode.LOTTO_6_42, before=date(2026, 1, 2)
    )

    assert [draw.draw_date for draw in before_target] == [date(2026, 1, 1)]
    database.dispose()



def test_paging_tied_dates_is_stable_filtered_and_bounded(db):
    import pytest
    repository = DrawRepository(db)
    repository.add_many(tuple(HistoricalDraw(game, date(2025,1,day), (1,2,3,4,5,6))
        for day in (1,2,3) for game in (GameCode.LOTTO_6_42, GameCode.MEGA_LOTTO_6_45)))
    expected = repository.list_draws(newest_first=True)
    paged = tuple(draw for offset in (0,2,4)
                  for draw in repository.list_draws(newest_first=True, limit=2, offset=offset))
    assert paged == expected
    assert len({(draw.game_code, draw.draw_date) for draw in paged}) == 6
    assert repository.list_draws(limit=2, offset=6) == ()
    filtered = repository.list_draws(game_code=GameCode.LOTTO_6_42,
        before=date(2025,1,3), newest_first=True, limit=1, offset=1)
    assert len(filtered) == 1 and filtered[0].draw_date == date(2025,1,1)
    with pytest.raises(ValueError):
        repository.list_draws(offset=-1)
