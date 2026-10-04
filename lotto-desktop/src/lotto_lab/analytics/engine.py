"""Pure historical characteristic calculations with explicit point-in-time inputs."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass

from lotto_lab.domain import GameCode, HistoricalDraw, number_group_index
from lotto_lab.analytics.range_analyzer import RangeAnalyzer, RangeStatistics


def longest_consecutive_run(numbers: tuple[int, ...]) -> int:
    longest = current = 1
    ordered = sorted(numbers)
    for previous, current_number in zip(ordered, ordered[1:], strict=False):
        current = current + 1 if current_number == previous + 1 else 1
        longest = max(longest, current)
    return longest


def sequence_category(numbers: tuple[int, ...]) -> str:
    longest = longest_consecutive_run(numbers)
    if longest == 1:
        return "none"
    if longest == 2:
        return "2"
    if longest == 3:
        return "3"
    return "4+"


def maximum_group_concentration(numbers: tuple[int, ...]) -> int:
    counts = Counter(number_group_index(number) for number in numbers)
    return max(counts.values(), default=0)


def odd_count(numbers: tuple[int, ...]) -> int:
    return sum(number % 2 for number in numbers)


@dataclass(frozen=True, slots=True)
class AnalyticsSnapshot:
    game_code: GameCode
    maximum_number: int
    draw_count: int
    number_frequencies: dict[int, int]
    cross_game_occurrences: dict[int, int]
    sequence_distribution: dict[str, int]
    bucket_distribution: dict[int, int]
    odd_even_distribution: dict[int, int]
    range_statistics: RangeStatistics | None = None

    def frequency_ratio(self, number: int) -> float:
        if not self.draw_count:
            return 0.0
        return self.number_frequencies.get(number, 0) / self.draw_count


class AnalyticsEngine:
    def analyze(
        self,
        *,
        game_code: GameCode,
        maximum_number: int,
        game_draws: tuple[HistoricalDraw, ...],
        cross_game_draws: tuple[HistoricalDraw, ...],
    ) -> AnalyticsSnapshot:
        frequencies: Counter[int] = Counter()
        sequences: Counter[str] = Counter()
        buckets: Counter[int] = Counter()
        parity: Counter[int] = Counter()
        cross_games: dict[int, set[GameCode]] = defaultdict(set)

        for draw in game_draws:
            frequencies.update(draw.numbers)
            sequences[sequence_category(draw.numbers)] += 1
            buckets[maximum_group_concentration(draw.numbers)] += 1
            parity[odd_count(draw.numbers)] += 1

        for draw in cross_game_draws:
            for number in draw.numbers:
                cross_games[number].add(draw.game_code)

        return AnalyticsSnapshot(
            game_code=game_code,
            maximum_number=maximum_number,
            draw_count=len(game_draws),
            number_frequencies={number: frequencies[number] for number in range(1, maximum_number + 1)},
            cross_game_occurrences={number: len(cross_games[number]) for number in range(1, maximum_number + 1)},
            sequence_distribution={key: sequences[key] for key in ("none", "2", "3", "4+")},
            bucket_distribution={count: buckets[count] for count in range(1, 7)},
            odd_even_distribution={count: parity[count] for count in range(0, 7)},
            range_statistics=RangeAnalyzer().calculate_range_statistics(game_draws, maximum_number),
        )
