"""Read and seed immutable strategy configuration snapshots."""

from __future__ import annotations

from sqlalchemy import select, func, update, text
from sqlalchemy.orm import selectinload

from lotto_lab.persistence.database import Database
from lotto_lab.persistence.models import Strategy, StrategyParameter, StrategyVersion
from lotto_lab.strategy.config import BUILT_IN_STRATEGIES, JONATHAN_RANGE_CONFIG, StrategyConfig


class StrategyRepository:
    CONFIG_KEY = "config"

    def __init__(self, database: Database) -> None:
        self.database = database

    def seed_built_ins(self) -> None:
        with self.database.session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            existing_labels = set(session.scalars(select(StrategyVersion.label)))
            for label, config in BUILT_IN_STRATEGIES.items():
                if label in existing_labels:
                    continue
                family_name, version_text = label.rsplit(" v", maxsplit=1)
                strategy = session.scalar(select(Strategy).where(Strategy.name == family_name))
                if strategy is None:
                    strategy = Strategy(
                        name=family_name,
                        description="Built-in transparent weighting strategy.",
                    )
                    session.add(strategy)
                version = StrategyVersion(
                    strategy=strategy,
                    version=int(version_text),
                    label=label,
                    is_locked=False,
                )
                version.parameters.append(
                    StrategyParameter(
                        key=self.CONFIG_KEY,
                        value_json=config.to_json(),
                        description="Complete immutable weighting configuration.",
                    )
                )
                session.add(version)
            session.flush()
            marker = "jonathan_range_reference"
            if session.scalar(select(StrategyParameter.id).where(StrategyParameter.key == marker)) is None:
                family = session.scalar(select(Strategy).where(Strategy.name == "Jonathan Weighted"))
                number = session.scalar(select(func.max(StrategyVersion.version)).where(
                    StrategyVersion.strategy_id == family.id)) + 1
                enhanced = StrategyVersion(strategy=family, version=number,
                    label=f"Jonathan Weighted v{number}", is_locked=True)
                enhanced.parameters = [
                    StrategyParameter(key=self.CONFIG_KEY, value_json=JONATHAN_RANGE_CONFIG.to_json(),
                        description="Jonathan Weighted with soft range composition and high-number balance."),
                    StrategyParameter(key=marker, value_json="true",
                        description="Built-in range enhancement reference; v1 remains unchanged."),
                ]
                session.add(enhanced)

    def list_versions(self) -> tuple[tuple[int, str], ...]:
        with self.database.session() as session:
            rows = session.execute(
                select(StrategyVersion.id, StrategyVersion.label).order_by(StrategyVersion.label)
            ).all()
            return tuple((row.id, row.label) for row in rows)

    def get_config(self, version_id: int) -> tuple[str, StrategyConfig]:
        statement = (
            select(StrategyVersion)
            .where(StrategyVersion.id == version_id)
            .options(selectinload(StrategyVersion.parameters))
        )
        with self.database.session() as session:
            version = session.scalar(statement)
            if version is None:
                raise LookupError(f"Strategy version does not exist: {version_id}")
            parameter = next(
                (item for item in version.parameters if item.key == self.CONFIG_KEY), None
            )
            if parameter is None:
                raise ValueError(f"Strategy version {version.label} has no configuration")
            return version.label, StrategyConfig.from_json(parameter.value_json)

    def lock(self, version_id: int) -> None:
        with self.database.session() as session:
            version = session.get(StrategyVersion, version_id)
            if version is None:
                raise LookupError(f"Strategy version does not exist: {version_id}")
            version.is_locked = True

    def is_locked(self, version_id: int) -> bool:
        with self.database.session() as session:
            version = session.get(StrategyVersion, version_id)
            if version is None:
                raise LookupError("Strategy version does not exist")
            return version.is_locked or version.label in BUILT_IN_STRATEGIES

    def save_config(self, version_id: int, config: StrategyConfig) -> None:
        """Serialize writes with use/locking so a used snapshot cannot change."""
        with self.database.session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            version = session.get(StrategyVersion, version_id)
            if version is None:
                raise LookupError("Strategy version does not exist")
            if version.is_locked or version.label in BUILT_IN_STRATEGIES:
                raise ValueError("This version is read-only. Clone it to make changes.")
            session.execute(update(StrategyParameter).where(
                StrategyParameter.strategy_version_id == version_id,
                StrategyParameter.key == self.CONFIG_KEY,
            ).values(value_json=config.to_json()))

    def clone(self, version_id: int) -> int:
        with self.database.session() as session:
            session.execute(text("BEGIN IMMEDIATE"))
            source = session.get(StrategyVersion, version_id)
            if source is None:
                raise LookupError("Strategy version does not exist")
            number = session.scalar(select(func.max(StrategyVersion.version)).where(
                StrategyVersion.strategy_id == source.strategy_id)) + 1
            clone = StrategyVersion(strategy_id=source.strategy_id, version=number,
                label=f"{source.strategy.name} v{number}", is_locked=False)
            clone.parameters = [StrategyParameter(key=p.key, value_json=p.value_json,
                description=p.description) for p in source.parameters if p.key == self.CONFIG_KEY]
            session.add(clone)
            session.flush()
            return clone.id

    def acquire_config(self, version_id: int) -> tuple[str, StrategyConfig]:
        # Lock before reading: concurrent editors cannot change the configuration
        # between generation and transactional ticket persistence.
        self.lock(version_id)
        return self.get_config(version_id)
