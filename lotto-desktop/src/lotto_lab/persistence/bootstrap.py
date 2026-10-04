"""Idempotent seed data needed by a new Lotto Lab database."""

from __future__ import annotations

from sqlalchemy import select

from lotto_lab.domain import SUPPORTED_GAMES
from lotto_lab.persistence.database import Database
from lotto_lab.persistence.models import Game
from lotto_lab.strategy.repository import StrategyRepository


def seed_supported_games(database: Database) -> None:
    with database.session() as session:
        existing_codes = set(session.scalars(select(Game.code)))
        session.add_all(
            Game(
                code=definition.code.value,
                name=definition.name,
                picks=definition.picks,
                maximum_number=definition.maximum_number,
            )
            for definition in SUPPORTED_GAMES
            if definition.code.value not in existing_codes
        )


def seed_application_data(database: Database) -> None:
    seed_supported_games(database)
    StrategyRepository(database).seed_built_ins()
