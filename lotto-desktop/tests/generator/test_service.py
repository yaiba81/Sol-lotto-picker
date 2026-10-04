from datetime import date

from sqlalchemy import func, select

from lotto_lab.analytics.service import AnalyticsService
from lotto_lab.domain import GameCode
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.generator.engine import seeded_generator
from lotto_lab.generator.repository import TicketRepository
from lotto_lab.generator.service import GeneratorService
from lotto_lab.persistence.bootstrap import seed_application_data
from lotto_lab.persistence.database import Database
from lotto_lab.persistence.models import GeneratedTicket, StrategyVersion
from lotto_lab.strategy.repository import StrategyRepository


def test_service_generates_persists_and_locks_strategy(tmp_path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'generator.sqlite3').as_posix()}")
    database.create_schema()
    seed_application_data(database)
    strategies = StrategyRepository(database)
    pure_id = next(identifier for identifier, label in strategies.list_versions() if label == "Pure Random v1")
    service = GeneratorService(
        AnalyticsService(DrawRepository(database)),
        strategies,
        TicketRepository(database),
        seeded_generator(42),
    )

    combinations = service.generate(
        game_code=GameCode.LOTTO_6_42,
        strategy_version_id=pure_id,
        window=100,
        ticket_count=2,
        cutoff=date(2026, 1, 1),
    )

    assert len(combinations) == 2
    assert all(item.historical_pattern_score == 50.0 for item in combinations)
    with database.session() as session:
        assert session.scalar(select(func.count(GeneratedTicket.id))) == 2
        assert session.get(StrategyVersion, pure_id).is_locked is True
    database.dispose()

