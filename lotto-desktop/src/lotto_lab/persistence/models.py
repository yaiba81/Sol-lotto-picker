"""Normalized persistence models for historical, strategy, and experiment data."""

from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from lotto_lab.persistence.base import Base


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class Game(Base):
    __tablename__ = "game"
    __table_args__ = (
        CheckConstraint("picks > 0", name="ck_game_picks_positive"),
        CheckConstraint("maximum_number >= picks", name="ck_game_valid_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    picks: Mapped[int] = mapped_column(Integer, nullable=False, default=6)
    maximum_number: Mapped[int] = mapped_column(Integer, nullable=False)

    draws: Mapped[list[Draw]] = relationship(back_populates="game")
    tickets: Mapped[list[GeneratedTicket]] = relationship(back_populates="game")


class Draw(Base):
    __tablename__ = "draw"
    __table_args__ = (UniqueConstraint("game_id", "draw_date", name="uq_draw_game_date"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("game.id"), nullable=False, index=True)
    draw_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    source: Mapped[str | None] = mapped_column(String(500))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    game: Mapped[Game] = relationship(back_populates="draws")
    numbers: Mapped[list[DrawNumber]] = relationship(
        back_populates="draw", cascade="all, delete-orphan", order_by="DrawNumber.position"
    )


class DrawNumber(Base):
    __tablename__ = "draw_number"
    __table_args__ = (
        UniqueConstraint("draw_id", "position", name="uq_draw_number_position"),
        UniqueConstraint("draw_id", "number", name="uq_draw_number_value"),
        CheckConstraint("position BETWEEN 1 AND 6", name="ck_draw_number_position"),
        CheckConstraint("number > 0", name="ck_draw_number_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    draw_id: Mapped[int] = mapped_column(ForeignKey("draw.id", ondelete="CASCADE"), nullable=False)
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    draw: Mapped[Draw] = relationship(back_populates="numbers")


class Strategy(Base):
    __tablename__ = "strategy"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    versions: Mapped[list[StrategyVersion]] = relationship(
        back_populates="strategy", cascade="all, delete-orphan"
    )


class StrategyVersion(Base):
    __tablename__ = "strategy_version"
    __table_args__ = (
        UniqueConstraint("strategy_id", "version", name="uq_strategy_version"),
        CheckConstraint("version > 0", name="ck_strategy_version_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_id: Mapped[int] = mapped_column(ForeignKey("strategy.id"), nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    label: Mapped[str] = mapped_column(String(160), nullable=False)
    is_locked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)

    strategy: Mapped[Strategy] = relationship(back_populates="versions")
    parameters: Mapped[list[StrategyParameter]] = relationship(
        back_populates="strategy_version", cascade="all, delete-orphan"
    )
    tickets: Mapped[list[GeneratedTicket]] = relationship(back_populates="strategy_version")


class StrategyParameter(Base):
    __tablename__ = "strategy_parameter"
    __table_args__ = (UniqueConstraint("strategy_version_id", "key", name="uq_strategy_parameter"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    strategy_version_id: Mapped[int] = mapped_column(
        ForeignKey("strategy_version.id", ondelete="CASCADE"), nullable=False
    )
    key: Mapped[str] = mapped_column(String(100), nullable=False)
    value_json: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str] = mapped_column(Text, default="", nullable=False)

    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="parameters")


class GeneratedTicket(Base):
    __tablename__ = "generated_ticket"
    __table_args__ = (
        CheckConstraint(
            "historical_pattern_score BETWEEN 0 AND 100",
            name="ck_ticket_pattern_score",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    game_id: Mapped[int] = mapped_column(ForeignKey("game.id"), nullable=False)
    strategy_version_id: Mapped[int] = mapped_column(ForeignKey("strategy_version.id"), nullable=False)
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    historical_cutoff: Mapped[date | None] = mapped_column(Date)
    historical_pattern_score: Mapped[float] = mapped_column(Float, nullable=False, default=0.0)
    explanation_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)

    game: Mapped[Game] = relationship(back_populates="tickets")
    strategy_version: Mapped[StrategyVersion] = relationship(back_populates="tickets")
    numbers: Mapped[list[GeneratedTicketNumber]] = relationship(
        back_populates="ticket", cascade="all, delete-orphan", order_by="GeneratedTicketNumber.position"
    )


class GeneratedTicketNumber(Base):
    __tablename__ = "generated_ticket_number"
    __table_args__ = (
        UniqueConstraint("ticket_id", "position", name="uq_ticket_number_position"),
        UniqueConstraint("ticket_id", "number", name="uq_ticket_number_value"),
        CheckConstraint("position BETWEEN 1 AND 6", name="ck_ticket_number_position"),
        CheckConstraint("number > 0", name="ck_ticket_number_positive"),
        CheckConstraint("final_weight >= 0", name="ck_ticket_number_weight"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    ticket_id: Mapped[int] = mapped_column(
        ForeignKey("generated_ticket.id", ondelete="CASCADE"), nullable=False
    )
    position: Mapped[int] = mapped_column(Integer, nullable=False)
    number: Mapped[int] = mapped_column(Integer, nullable=False)
    final_weight: Mapped[Decimal] = mapped_column(Numeric(18, 10), nullable=False)
    factors_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    explanation: Mapped[str] = mapped_column(Text, default="", nullable=False)

    ticket: Mapped[GeneratedTicket] = relationship(back_populates="numbers")


class BacktestRun(Base):
    __tablename__ = "backtest_run"
    __table_args__ = (CheckConstraint("tickets_per_draw > 0", name="ck_backtest_ticket_count"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    game_id: Mapped[int] = mapped_column(ForeignKey("game.id"), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utc_now)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), default="pending", nullable=False)
    first_draw_date: Mapped[date] = mapped_column(Date, nullable=False)
    last_draw_date: Mapped[date] = mapped_column(Date, nullable=False)
    tickets_per_draw: Mapped[int] = mapped_column(Integer, nullable=False)
    random_seed: Mapped[str | None] = mapped_column(String(128))

    results: Mapped[list[BacktestResult]] = relationship(
        back_populates="run", cascade="all, delete-orphan"
    )


class BacktestResult(Base):
    __tablename__ = "backtest_result"
    __table_args__ = (
        UniqueConstraint(
            "backtest_run_id",
            "strategy_version_id",
            "match_count",
            name="uq_backtest_strategy_match_count",
        ),
        CheckConstraint("match_count BETWEEN 0 AND 6", name="ck_backtest_match_count"),
        CheckConstraint("occurrences >= 0", name="ck_backtest_occurrences"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    backtest_run_id: Mapped[int] = mapped_column(
        ForeignKey("backtest_run.id", ondelete="CASCADE"), nullable=False
    )
    strategy_version_id: Mapped[int] = mapped_column(ForeignKey("strategy_version.id"), nullable=False)
    match_count: Mapped[int] = mapped_column(Integer, nullable=False)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
    average_matches: Mapped[float] = mapped_column(Float, nullable=False)
    variance: Mapped[float] = mapped_column(Float, nullable=False)
    confidence_low: Mapped[float | None] = mapped_column(Float)
    confidence_high: Mapped[float | None] = mapped_column(Float)

    run: Mapped[BacktestRun] = relationship(back_populates="results")



class BacktestSettings(Base):
    """Additive Phase 6 table; existing databases retain all historical rows."""
    __tablename__ = "backtest_settings"
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_run.id", ondelete="CASCADE"), primary_key=True)
    historical_window: Mapped[int] = mapped_column(Integer, nullable=False)


class BacktestRangePattern(Base):
    """Additive aggregate table, one row per run/version/generated range pattern."""
    __tablename__ = "backtest_range_pattern"
    __table_args__ = (CheckConstraint("occurrences >= 0", name="ck_range_pattern_occurrences"),)
    run_id: Mapped[int] = mapped_column(ForeignKey("backtest_run.id", ondelete="CASCADE"), primary_key=True)
    strategy_version_id: Mapped[int] = mapped_column(ForeignKey("strategy_version.id"), primary_key=True)
    pattern: Mapped[str] = mapped_column(String(24), primary_key=True)
    occurrences: Mapped[int] = mapped_column(Integer, nullable=False)
