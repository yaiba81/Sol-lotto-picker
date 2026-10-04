"""Historical draw persistence boundary."""

from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from lotto_lab.domain import GameCode, HistoricalDraw
from lotto_lab.persistence.database import Database
from lotto_lab.persistence.models import Draw, DrawNumber, Game


class DrawRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def add_many(self, draws: tuple[HistoricalDraw, ...], *, source: str | None = None) -> int:
        inserted = 0
        with self.database.session() as session:
            games = {GameCode(game.code): game for game in session.scalars(select(Game))}
            existing = set(
                session.execute(select(Draw.game_id, Draw.draw_date)).tuples().all()
            )
            for item in draws:
                game = games[item.game_code]
                identity = (game.id, item.draw_date)
                if identity in existing:
                    continue
                entity = Draw(game=game, draw_date=item.draw_date, source=source)
                entity.numbers = [
                    DrawNumber(position=position, number=number)
                    for position, number in enumerate(item.numbers, start=1)
                ]
                session.add(entity)
                existing.add(identity)
                inserted += 1
        return inserted

    def list_draws(
        self,
        *,
        game_code: GameCode | str | None = None,
        before: date | None = None,
        limit: int | None = None,
        newest_first: bool = False,
        offset: int = 0,
    ) -> tuple[HistoricalDraw, ...]:
        if offset < 0:
            raise ValueError("Offset cannot be negative")
        statement = (
            select(Draw)
            .join(Draw.game)
            .options(selectinload(Draw.numbers), selectinload(Draw.game))
        )
        if game_code is not None:
            statement = statement.where(Game.code == GameCode(game_code).value)
        if before is not None:
            statement = statement.where(Draw.draw_date < before)
        statement = statement.order_by(
            Draw.draw_date.desc() if newest_first else Draw.draw_date.asc(), Draw.id.asc()
        ).offset(offset)
        if limit is not None:
            if limit <= 0:
                return ()
            statement = statement.limit(limit)
        with self.database.session() as session:
            entities = session.scalars(statement).all()
            return tuple(
                HistoricalDraw(
                    game_code=GameCode(entity.game.code),
                    draw_date=entity.draw_date,
                    numbers=tuple(number.number for number in entity.numbers),
                )
                for entity in entities
            )

    def count(self, game_code: GameCode | str | None = None) -> int:
        from sqlalchemy import func

        statement = select(func.count(Draw.id)).join(Draw.game)
        if game_code is not None:
            statement = statement.where(Game.code == GameCode(game_code).value)
        with self.database.session() as session:
            return int(session.scalar(statement) or 0)
