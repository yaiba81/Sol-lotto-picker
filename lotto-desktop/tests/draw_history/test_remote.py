import json
from datetime import date, timedelta
from urllib.parse import parse_qs, urlparse

import pytest

from lotto_lab.domain import GameCode, HistoricalDraw
from lotto_lab.draw_history.remote import OfficialResultsClient, PublicResultsClient, ResultsSyncService
from lotto_lab.draw_history.repository import DrawRepository
from lotto_lab.persistence.bootstrap import seed_supported_games
from lotto_lab.persistence.database import Database


class FakeResponse:
    def __init__(self, document: object) -> None:
        self.payload = json.dumps(document).encode()

    def read(self, size: int = -1) -> bytes:
        return self.payload[:size]

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return None


def test_official_client_builds_bounded_query_and_validates_draw() -> None:
    captured = {}

    def opener(request, timeout):
        captured["url"] = request.full_url
        captured["timeout"] = timeout
        return FakeResponse(
            {
                "items": [
                    {
                        "drawDate": "2026-01-02",
                        "result": ["01", "07", "12", "19", "31", "42"],
                    }
                ]
            }
        )

    draws = OfficialResultsClient(timeout=3, opener=opener).fetch_recent(
        GameCode.LOTTO_6_42, limit=20
    )

    query = parse_qs(urlparse(captured["url"]).query)
    assert query == {"lottery": ["LOTTO42"], "page": ["1"], "perPage": ["20"]}
    assert captured["timeout"] == 3
    assert draws == (
        HistoricalDraw(GameCode.LOTTO_6_42, date(2026, 1, 2), (1, 7, 12, 19, 31, 42)),
    )


def test_official_client_rejects_future_or_out_of_range_data() -> None:
    future = (date.today() + timedelta(days=1)).isoformat()
    client = OfficialResultsClient(
        opener=lambda request, timeout: FakeResponse(
            {"items": [{"drawDate": future, "result": [1, 2, 3, 4, 5, 42]}]}
        )
    )

    with pytest.raises(ValueError, match="future"):
        client.fetch_recent(GameCode.LOTTO_6_42)


def test_sync_keeps_successful_games_when_one_feed_fails(tmp_path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'sync.sqlite3').as_posix()}")
    database.create_schema()
    seed_supported_games(database)
    repository = DrawRepository(database)

    class PartialClient:
        def fetch_recent(self, game_code, *, limit):
            if game_code == GameCode.MEGA_LOTTO_6_45:
                raise ConnectionError("offline")
            maximum = {
                GameCode.LOTTO_6_42: 42,
                GameCode.SUPER_LOTTO_6_49: 49,
                GameCode.GRAND_LOTTO_6_55: 55,
                GameCode.ULTRA_LOTTO_6_58: 58,
            }[game_code]
            return (
                HistoricalDraw(game_code, date(2026, 1, 1), (1, 2, 3, 4, 5, maximum)),
            )

    result = ResultsSyncService(repository, PartialClient()).synchronize(per_game=10)

    assert result.fetched == 4
    assert result.inserted == 4
    assert result.rejected == 1
    assert len(result.outdated) == 4
    assert repository.count() == 4
    database.dispose()


def test_public_page_matches_dated_links_to_numbers() -> None:
    page = '''<script type="application/ld+json">{"@type":"ItemList",
    "@id":"https://lotto.works/en/results/lotto-6-42/#visible-results",
    "itemListElement":[{"item":{"url":"https://lotto.works/en/results/lotto-6-42/2026-10-22/9pm/"}}]}
    </script><ol data-winning-numbers><li>22</li><li>42</li><li>37</li><li>21</li><li>08</li><li>17</li></ol>'''
    client = PublicResultsClient(opener=lambda request, timeout: FakeHtmlResponse(page))

    assert client.fetch_recent(GameCode.LOTTO_6_42, limit=1) == (
        HistoricalDraw(GameCode.LOTTO_6_42, date(2026, 10, 22), (22, 42, 37, 21, 8, 17)),
    )
    with pytest.raises(ValueError, match="dates and numbers"):
        PublicResultsClient.parse_page(GameCode.LOTTO_6_42, page.replace("data-winning-numbers", "data-other"))
    with pytest.raises(ValueError, match="dates and numbers"):
        PublicResultsClient.parse_page(GameCode.MEGA_LOTTO_6_45, page)


class FakeHtmlResponse(FakeResponse):
    def __init__(self, html: str) -> None:
        self.payload = html.encode()


def test_sync_falls_back_and_preserves_conflicting_history(tmp_path) -> None:
    database = Database(f"sqlite:///{(tmp_path / 'fallback.sqlite3').as_posix()}")
    database.create_schema()
    seed_supported_games(database)
    repository = DrawRepository(database)
    old = HistoricalDraw(GameCode.LOTTO_6_42, date(2026, 1, 1), (1, 2, 3, 4, 5, 42))
    repository.add_many((old,), source="original")

    class BrokenClient:
        def fetch_recent(self, game_code, *, limit):
            raise ConnectionError("primary unavailable")

    class BackupClient:
        source = "backup"

        def fetch_recent(self, game_code, *, limit):
            maximum = {"6/42": 42, "6/45": 45, "6/49": 49, "6/55": 55, "6/58": 58}[game_code.value]
            numbers = (1, 2, 3, 4, 6, maximum) if game_code == GameCode.LOTTO_6_42 else (1, 2, 3, 4, 5, maximum)
            return (HistoricalDraw(game_code, date(2026, 1, 1), numbers),)

    result = ResultsSyncService(repository, BrokenClient(), BackupClient()).synchronize(per_game=1)

    assert len(result.failovers) == 5
    assert result.rejected == 1
    assert repository.list_draws(game_code=GameCode.LOTTO_6_42) == (old,)
    assert repository.count() == 5
    database.dispose()

