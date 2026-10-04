"""Validated synchronization from PCSO LottoMatik's public results service."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date
from collections.abc import Callable
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from lotto_lab.domain import GameCode, HistoricalDraw, SUPPORTED_GAMES
from lotto_lab.draw_history.repository import DrawRepository


OFFICIAL_RESULTS_ORIGIN = "https://lottomatik.pcso.gov.ph"
HISTORY_ENDPOINT = f"{OFFICIAL_RESULTS_ORIGIN}/api/backend/get-game-history"
REMOTE_GAME_CODES: dict[GameCode, str] = {
    GameCode.LOTTO_6_42: "LOTTO42",
    GameCode.MEGA_LOTTO_6_45: "ML45",
    GameCode.SUPER_LOTTO_6_49: "SL49",
    GameCode.GRAND_LOTTO_6_55: "GL55",
    GameCode.ULTRA_LOTTO_6_58: "UL58",
}


class ResponseLike(Protocol):
    def read(self, size: int = -1) -> bytes: ...
    def __enter__(self) -> "ResponseLike": ...
    def __exit__(self, *args: object) -> None: ...


class Opener(Protocol):
    def __call__(self, request: Request, timeout: float) -> ResponseLike: ...


@dataclass(frozen=True, slots=True)
class SyncResult:
    fetched: int
    inserted: int
    rejected: int
    errors: tuple[str, ...]


class OfficialResultsClient:
    """Small HTTP client with bounded responses and no persistence side effects."""

    MAX_RESPONSE_BYTES = 2_000_000

    def __init__(self, *, timeout: float = 6.0, opener: Opener = urlopen) -> None:
        self.timeout = timeout
        self.opener = opener

    def fetch_recent(self, game_code: GameCode, *, limit: int = 50) -> tuple[HistoricalDraw, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("Remote history limit must be between 1 and 100")
        query = urlencode(
            {"lottery": REMOTE_GAME_CODES[game_code], "page": 1, "perPage": limit}
        )
        url = f"{HISTORY_ENDPOINT}?{query}"
        request = Request(
            url,
            headers={
                "Accept": "application/json",
                "User-Agent": "Lotto-Lab/0.1 (+local desktop historical research)",
            },
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = response.read(self.MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ConnectionError(f"Official results request failed: {exc}") from exc
        if len(payload) > self.MAX_RESPONSE_BYTES:
            raise ValueError("Official results response exceeded the safety limit")
        try:
            document = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Official results response was not valid JSON") from exc
        items = document.get("items") if isinstance(document, dict) else None
        if not isinstance(items, list):
            raise ValueError("Official results response did not contain an items list")

        draws: list[HistoricalDraw] = []
        for item in items:
            draws.append(self._parse_item(game_code, item))
        return tuple(draws)

    @staticmethod
    def _parse_item(game_code: GameCode, item: Any) -> HistoricalDraw:
        if not isinstance(item, dict):
            raise ValueError("Official result item was not an object")
        try:
            draw_date = date.fromisoformat(item["drawDate"])
            numbers = tuple(int(number) for number in item["result"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError("Official result item had invalid fields") from exc
        if draw_date > date.today():
            raise ValueError(f"Official result had a future draw date: {draw_date}")
        return HistoricalDraw(game_code, draw_date, numbers)


class ResultsSyncService:
    def __init__(
        self,
        repository: DrawRepository,
        client: OfficialResultsClient | None = None,
    ) -> None:
        self.repository = repository
        self.client = client or OfficialResultsClient()

    def synchronize(
        self,
        *,
        per_game: int = 50,
        should_cancel: Callable[[], bool] | None = None,
    ) -> SyncResult:
        fetched: list[HistoricalDraw] = []
        rejected = 0
        errors: list[str] = []
        for game in SUPPORTED_GAMES:
            if should_cancel and should_cancel():
                errors.append("Synchronization cancelled")
                break
            try:
                fetched.extend(self.client.fetch_recent(game.code, limit=per_game))
            except (ConnectionError, ValueError) as exc:
                rejected += 1
                errors.append(f"{game.name}: {exc}")
        inserted = self.repository.add_many(
            tuple(fetched), source=HISTORY_ENDPOINT
        )
        return SyncResult(len(fetched), inserted, rejected, tuple(errors))
