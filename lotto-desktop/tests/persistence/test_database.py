from __future__ import annotations

from pathlib import Path

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from lotto_lab.persistence.bootstrap import seed_supported_games
from lotto_lab.persistence.database import Database
from lotto_lab.persistence.models import Game, Strategy, StrategyVersion


@pytest.fixture
def database(tmp_path: Path):
    db = Database(f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}")
    db.create_schema()
    yield db
    db.dispose()


def test_supported_game_seed_is_idempotent(database: Database) -> None:
    seed_supported_games(database)
    seed_supported_games(database)

    with database.session() as session:
        assert session.scalar(select(func.count(Game.id))) == 5


def test_strategy_version_number_is_unique_per_strategy(database: Database) -> None:
    with pytest.raises(IntegrityError):
        with database.session() as session:
            strategy = Strategy(name="Jonathan Weighted", description="Test")
            strategy.versions = [
                StrategyVersion(version=1, label="Jonathan Weighted v1"),
                StrategyVersion(version=1, label="Duplicate version"),
            ]
            session.add(strategy)


def test_transaction_rolls_back_after_error(database: Database) -> None:
    with pytest.raises(RuntimeError):
        with database.session() as session:
            session.add(Strategy(name="Temporary", description=""))
            raise RuntimeError("abort")

    with database.session() as session:
        assert session.scalar(select(func.count(Strategy.id))) == 0

