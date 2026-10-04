"""Stable domain vocabulary shared across Lotto Lab modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from enum import StrEnum


class GameCode(StrEnum):
    LOTTO_6_42 = "6/42"
    MEGA_LOTTO_6_45 = "6/45"
    SUPER_LOTTO_6_49 = "6/49"
    GRAND_LOTTO_6_55 = "6/55"
    ULTRA_LOTTO_6_58 = "6/58"


@dataclass(frozen=True, slots=True)
class GameDefinition:
    code: GameCode
    name: str
    maximum_number: int
    picks: int = 6

    def validate_numbers(self, numbers: tuple[int, ...]) -> None:
        if len(numbers) != self.picks:
            raise ValueError(f"{self.name} requires exactly {self.picks} numbers")
        if len(set(numbers)) != len(numbers):
            raise ValueError("Numbers must be distinct")
        if any(number < 1 or number > self.maximum_number for number in numbers):
            raise ValueError(f"Numbers must be between 1 and {self.maximum_number}")


@dataclass(frozen=True, slots=True)
class HistoricalDraw:
    game_code: GameCode
    draw_date: date
    numbers: tuple[int, ...]

    def __post_init__(self) -> None:
        definition = game_definition(self.game_code)
        definition.validate_numbers(self.numbers)


SUPPORTED_GAMES: tuple[GameDefinition, ...] = (
    GameDefinition(GameCode.LOTTO_6_42, "Lotto 6/42", 42),
    GameDefinition(GameCode.MEGA_LOTTO_6_45, "Mega Lotto 6/45", 45),
    GameDefinition(GameCode.SUPER_LOTTO_6_49, "Super Lotto 6/49", 49),
    GameDefinition(GameCode.GRAND_LOTTO_6_55, "Grand Lotto 6/55", 55),
    GameDefinition(GameCode.ULTRA_LOTTO_6_58, "Ultra Lotto 6/58", 58),
)


NUMBER_GROUPS: tuple[range, ...] = (
    range(1, 11),
    range(11, 20),
    range(20, 30),
    range(30, 40),
    range(40, 50),
    range(50, 59),
)


def game_definition(code: GameCode | str) -> GameDefinition:
    normalized = GameCode(code)
    return next(game for game in SUPPORTED_GAMES if game.code == normalized)


def number_group_index(number: int) -> int:
    for index, group in enumerate(NUMBER_GROUPS):
        if number in group:
            return index
    raise ValueError(f"Number outside supported groups: {number}")
