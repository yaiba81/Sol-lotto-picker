"""Persist generated combinations and their complete explanation trail."""

from __future__ import annotations

import json
from datetime import date
from decimal import Decimal

from sqlalchemy import select

from lotto_lab.domain import GameCode
from lotto_lab.generator.models import GeneratedCombination
from lotto_lab.persistence.database import Database
from lotto_lab.persistence.models import Game, GeneratedTicket, GeneratedTicketNumber, StrategyVersion


class TicketRepository:
    def __init__(self, database: Database) -> None:
        self.database = database

    def save(
        self,
        combination: GeneratedCombination,
        *,
        game_code: GameCode,
        strategy_version_id: int,
        historical_cutoff: date,
    ) -> int:
        with self.database.session() as session:
            game = session.scalar(select(Game).where(Game.code == game_code.value))
            version = session.get(StrategyVersion, strategy_version_id)
            if game is None or version is None:
                raise LookupError("Game or strategy version does not exist")
            version.is_locked = True
            ticket = GeneratedTicket(
                game=game,
                strategy_version=version,
                historical_cutoff=historical_cutoff,
                historical_pattern_score=combination.historical_pattern_score,
                explanation_json=json.dumps(combination.summary_factors, sort_keys=True),
            )
            evaluations = {item.number: item for item in combination.selected_evaluations}
            ticket.numbers = [
                GeneratedTicketNumber(
                    position=position,
                    number=number,
                    final_weight=Decimal(str(evaluations[number].final_weight)),
                    factors_json=json.dumps(evaluations[number].factors, sort_keys=True),
                    explanation="; ".join(evaluations[number].explanations),
                )
                for position, number in enumerate(combination.numbers, start=1)
            ]
            session.add(ticket)
            session.flush()
            return ticket.id

