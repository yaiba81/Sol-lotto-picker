from datetime import date

from lotto_lab.analytics.engine import (
    AnalyticsEngine,
    maximum_group_concentration,
    odd_count,
    sequence_category,
)
from lotto_lab.domain import GameCode, HistoricalDraw


def test_characteristic_helpers_use_required_group_boundaries() -> None:
    assert sequence_category((1, 2, 4, 7, 9, 11)) == "2"
    assert sequence_category((10, 11, 12, 20, 30, 40)) == "3"
    assert maximum_group_concentration((1, 10, 11, 19, 20, 29)) == 2
    assert odd_count((1, 2, 3, 4, 5, 6)) == 3


def test_engine_calculates_frequency_and_cross_game_presence() -> None:
    selected = (
        HistoricalDraw(GameCode.LOTTO_6_42, date(2025, 1, 1), (1, 2, 3, 10, 20, 30)),
        HistoricalDraw(GameCode.LOTTO_6_42, date(2025, 1, 2), (1, 4, 5, 11, 21, 31)),
    )
    other = (
        HistoricalDraw(GameCode.MEGA_LOTTO_6_45, date(2025, 1, 1), (1, 2, 6, 12, 22, 32)),
    )

    snapshot = AnalyticsEngine().analyze(
        game_code=GameCode.LOTTO_6_42,
        maximum_number=42,
        game_draws=selected,
        cross_game_draws=selected + other,
    )

    assert snapshot.draw_count == 2
    assert snapshot.number_frequencies[1] == 2
    assert snapshot.cross_game_occurrences[1] == 2
    assert snapshot.cross_game_occurrences[30] == 1
    assert sum(snapshot.sequence_distribution.values()) == 2

