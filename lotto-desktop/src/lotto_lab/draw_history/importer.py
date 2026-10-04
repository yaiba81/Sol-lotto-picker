"""CSV parsing and validation for official historical draw data."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

from lotto_lab.domain import GameCode, HistoricalDraw


@dataclass(frozen=True, slots=True)
class ImportIssue:
    row_number: int
    message: str


@dataclass(frozen=True, slots=True)
class ParseResult:
    draws: tuple[HistoricalDraw, ...]
    issues: tuple[ImportIssue, ...]


class DrawCsvImporter:
    """Parse `game,date,n1..n6` CSV files without mutating persistence."""

    REQUIRED_COLUMNS = ("game", "date", "n1", "n2", "n3", "n4", "n5", "n6")
    DATE_FORMATS = ("%Y-%m-%d", "%m/%d/%Y", "%d/%m/%Y")

    def parse(self, path: Path) -> ParseResult:
        draws: list[HistoricalDraw] = []
        issues: list[ImportIssue] = []
        seen: set[tuple[GameCode, date]] = set()

        with path.open("r", encoding="utf-8-sig", newline="") as stream:
            reader = csv.DictReader(stream)
            normalized = {name.strip().lower() for name in (reader.fieldnames or [])}
            missing = set(self.REQUIRED_COLUMNS) - normalized
            if missing:
                raise ValueError(f"Missing CSV columns: {', '.join(sorted(missing))}")

            for row_number, raw in enumerate(reader, start=2):
                row = {key.strip().lower(): (value or "").strip() for key, value in raw.items()}
                try:
                    draw = HistoricalDraw(
                        game_code=self._parse_game(row["game"]),
                        draw_date=self._parse_date(row["date"]),
                        numbers=tuple(int(row[f"n{index}"]) for index in range(1, 7)),
                    )
                    identity = (draw.game_code, draw.draw_date)
                    if identity in seen:
                        raise ValueError("Duplicate game and draw date in CSV")
                    seen.add(identity)
                    draws.append(draw)
                except (TypeError, ValueError) as exc:
                    issues.append(ImportIssue(row_number, str(exc)))

        return ParseResult(tuple(draws), tuple(issues))

    @staticmethod
    def _parse_game(value: str) -> GameCode:
        aliases = {
            "lotto 6/42": GameCode.LOTTO_6_42,
            "mega lotto 6/45": GameCode.MEGA_LOTTO_6_45,
            "super lotto 6/49": GameCode.SUPER_LOTTO_6_49,
            "grand lotto 6/55": GameCode.GRAND_LOTTO_6_55,
            "ultra lotto 6/58": GameCode.ULTRA_LOTTO_6_58,
        }
        alias = aliases.get(value.casefold())
        return alias if alias is not None else GameCode(value)

    def _parse_date(self, value: str) -> date:
        for date_format in self.DATE_FORMATS:
            try:
                return date.fromisoformat(value) if date_format == "%Y-%m-%d" else datetime.strptime(
                    value, date_format
                ).date()
            except ValueError:
                continue
        raise ValueError(f"Unsupported date: {value!r}")
