"""Validated synchronization from public PCSO results sources."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from collections.abc import Callable
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from zoneinfo import ZoneInfo

from lotto_lab.domain import GameCode, HistoricalDraw, SUPPORTED_GAMES
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.schedule import ScheduleService


OFFICIAL_RESULTS_ORIGIN = "https://lottomatik.pcso.gov.ph"
HISTORY_ENDPOINT = f"{OFFICIAL_RESULTS_ORIGIN}/api/backend/get-game-history"
PUBLIC_RESULTS_ORIGIN = "https://lotto.works"
PUBLIC_RESULT_SLUGS: dict[GameCode, str] = {
    GameCode.LOTTO_6_42: "lotto-6-42",
    GameCode.MEGA_LOTTO_6_45: "mega-lotto-6-45",
    GameCode.SUPER_LOTTO_6_49: "super-lotto-6-49",
    GameCode.GRAND_LOTTO_6_55: "grand-lotto-6-55",
    GameCode.ULTRA_LOTTO_6_58: "ultra-lotto-6-58",
}
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
    outdated: tuple[str, ...] = ()
    failovers: tuple[str, ...] = ()


class OfficialResultsClient:
    """Small HTTP client with bounded responses and no persistence side effects."""

    MAX_RESPONSE_BYTES = 2_000_000
    source = HISTORY_ENDPOINT

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
        if draw_date > datetime.now(ZoneInfo("Asia/Manila")).date():
            raise ValueError(f"Official result had a future draw date: {draw_date}")
        return HistoricalDraw(game_code, draw_date, numbers)


class PublicResultsClient:
    """Read bounded public result pages; reject changed markup and game mappings."""

    MAX_RESPONSE_BYTES = 400_000
    source = PUBLIC_RESULTS_ORIGIN

    def __init__(self, *, timeout: float = 8.0, opener: Opener = urlopen) -> None:
        self.timeout = timeout
        self.opener = opener

    def fetch_recent(self, game_code: GameCode, *, limit: int = 50) -> tuple[HistoricalDraw, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("Remote history limit must be between 1 and 100")
        slug = PUBLIC_RESULT_SLUGS[game_code]
        request = Request(
            f"{PUBLIC_RESULTS_ORIGIN}/en/results/{slug}/",
            headers={"Accept": "text/html", "User-Agent": "Lotto-Lab/0.1 (+local desktop historical research)"},
        )
        try:
            with self.opener(request, timeout=self.timeout) as response:
                payload = response.read(self.MAX_RESPONSE_BYTES + 1)
        except (HTTPError, URLError, TimeoutError, OSError) as exc:
            raise ConnectionError(f"Public results request failed: {exc}") from exc
        if len(payload) > self.MAX_RESPONSE_BYTES:
            raise ValueError("Public results page exceeded the safety limit")
        try:
            html = payload.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ValueError("Public results page was not UTF-8") from exc
        return self.parse_page(game_code, html, limit=limit)

    @staticmethod
    def parse_page(game_code: GameCode, html: str, *, limit: int = 50) -> tuple[HistoricalDraw, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("Remote history limit must be between 1 and 100")
        slug = PUBLIC_RESULT_SLUGS[game_code]
        scripts = re.findall(
            r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
        )
        list_id = f"{PUBLIC_RESULTS_ORIGIN}/en/results/{slug}/#visible-results"
        listing: dict[str, Any] | None = None
        for script in scripts:
            try:
                value = json.loads(script)
            except json.JSONDecodeError:
                continue
            if isinstance(value, dict) and value.get("@type") == "ItemList" and value.get("@id") == list_id:
                listing = value
                break
        entries = listing.get("itemListElement") if listing else None
        ball_groups = re.findall(r"data-winning-numbers[^>]*>(.*?)</ol>", html, re.DOTALL)
        if not isinstance(entries, list) or not entries or len(entries) != len(ball_groups):
            raise ValueError("Public results dates and numbers did not match")
        url_pattern = re.compile(
            rf"^{re.escape(PUBLIC_RESULTS_ORIGIN)}/en/results/{re.escape(slug)}/(\d{{4}}-\d{{2}}-\d{{2}})/9pm/$"
        )
        draws: list[HistoricalDraw] = []
        seen: set[date] = set()
        for entry, group in zip(entries[:limit], ball_groups, strict=False):
            url = entry.get("item", {}).get("url") if isinstance(entry, dict) else None
            match = url_pattern.fullmatch(url) if isinstance(url, str) else None
            if match is None:
                raise ValueError("Public result game or draw URL was invalid")
            day = date.fromisoformat(match.group(1))
            numbers = tuple(int(number) for number in re.findall(r"<li>\s*(\d{1,2})\s*</li>", group))
            if day > datetime.now(ZoneInfo("Asia/Manila")).date() or day in seen:
                raise ValueError("Public result date was future or duplicated")
            seen.add(day)
            draws.append(HistoricalDraw(game_code, day, numbers))
        return tuple(draws)


class ResultsClient(Protocol):
    def fetch_recent(self, game_code: GameCode, *, limit: int) -> tuple[HistoricalDraw, ...]: ...


def latest_expected_date(game_code: GameCode, *, now: datetime | None = None,
                         schedule: ScheduleService | None = None) -> date | None:
    current = (now or datetime.now(ZoneInfo("Asia/Manila"))).astimezone(ZoneInfo("Asia/Manila"))
    game = next((item for item in (schedule or ScheduleService()).games
                 if item.code == game_code and item.active), None)
    if game is None:
        return None
    for offset in range(8):
        day = current.date() - timedelta(days=offset)
        if day.weekday() not in game.draw_days:
            continue
        if offset == 0 and current.time() < time(23):
            continue
        return day
    return None


class ResultsSyncService:
    def __init__(
        self,
        repository: DrawRepository,
        client: ResultsClient | None = None,
        fallback: ResultsClient | None = None,
        schedule: ScheduleService | None = None,
    ) -> None:
        self.repository = repository
        self.client = client or PublicResultsClient()
        self.fallback = fallback if client is not None else (fallback or OfficialResultsClient())
        self.schedule = schedule or ScheduleService()

    def synchronize(
        self,
        *,
        per_game: int = 50,
        should_cancel: Callable[[], bool] | None = None,
    ) -> SyncResult:
        fetched = 0
        inserted = 0
        rejected = 0
        errors: list[str] = []
        outdated: list[str] = []
        failovers: list[str] = []
        for game in SUPPORTED_GAMES:
            if should_cancel and should_cancel():
                errors.append("Synchronization cancelled")
                break
            try:
                draws = self.client.fetch_recent(game.code, limit=per_game)
                source = getattr(self.client, "source", PUBLIC_RESULTS_ORIGIN)
            except (ConnectionError, ValueError) as exc:
                if self.fallback is None:
                    rejected += 1
                    errors.append(f"{game.name}: {exc}")
                    continue
                failovers.append(f"{game.name}: {exc}")
                try:
                    draws = self.fallback.fetch_recent(game.code, limit=per_game)
                    source = getattr(self.fallback, "source", HISTORY_ENDPOINT)
                except (ConnectionError, ValueError) as fallback_exc:
                    rejected += 1
                    errors.append(f"{game.name}: {fallback_exc}")
                    continue
            if not draws:
                rejected += 1
                errors.append(f"{game.name}: no results returned")
                continue
            expected = latest_expected_date(game.code, schedule=self.schedule)
            if expected and max(draw.draw_date for draw in draws) < expected:
                outdated.append(game.name)
            existing = {draw.draw_date: draw for draw in self.repository.list_draws(
                game_code=game.code, newest_first=True
            )}
            accepted: list[HistoricalDraw] = []
            for draw in draws:
                prior = existing.get(draw.draw_date)
                if prior and set(prior.numbers) != set(draw.numbers):
                    rejected += 1
                    errors.append(f"{game.name} {draw.draw_date}: conflicting stored result; verification required")
                    continue
                accepted.append(draw)
            fetched += len(accepted)
            inserted += self.repository.add_many(tuple(accepted), source=source)
        return SyncResult(fetched, inserted, rejected, tuple(errors), tuple(outdated), tuple(failovers))
