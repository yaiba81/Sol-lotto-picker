"""Range composition, with exact finite-population uniform expectations.

These ranges intentionally differ from the legacy Jonathan bucket factor.
Frequencies describe the supplied sample, never future winning odds.
"""
from collections import Counter
from dataclasses import dataclass
from functools import lru_cache
from math import comb, prod

from lotto_lab.domain import HistoricalDraw


def number_ranges(game_max: int) -> tuple[range, ...]:
    if game_max not in (42, 45, 49, 55, 58):
        raise ValueError("Unsupported game maximum")
    return tuple(range(lo, min(hi, game_max) + 1)
                 for lo, hi in ((1, 9), (10, 19), (20, 29), (30, 39), (40, 49), (50, 58))
                 if lo <= game_max)


def range_pattern(numbers: tuple[int, ...], game_max: int) -> tuple[int, ...]:
    if len(numbers) > 6 or len(set(numbers)) != len(numbers):
        raise ValueError("At most six distinct numbers are required")
    if any(type(n) is not int or not 1 <= n <= game_max for n in numbers):
        raise ValueError("Numbers must be integers within the game range")
    return tuple(sum(n in bucket for n in numbers) for bucket in number_ranges(game_max))


def pattern_label(pattern: tuple[int, ...]) -> str:
    return "-".join(map(str, pattern))


@lru_cache(maxsize=5)
def uniform_patterns(game_max: int) -> tuple[tuple[tuple[int, ...], float], ...]:
    sizes = tuple(map(len, number_ranges(game_max)))
    def compositions(index, left, prefix):
        if index == len(sizes):
            if left == 0:
                yield prefix
            return
        for count in range(min(sizes[index], left) + 1):
            yield from compositions(index + 1, left - count, prefix + (count,))
    return tuple((p, prod(comb(size, k) for size, k in zip(sizes, p)) / comb(game_max, 6))
                 for p in compositions(0, 6, ()))


def expected_count_distribution(game_max: int, range_size: int) -> tuple[float, ...]:
    return tuple(comb(range_size, k) * comb(game_max - range_size, 6 - k) / comb(game_max, 6)
                 if k <= range_size and 6 - k <= game_max - range_size else 0.0
                 for k in range(7))


@dataclass(frozen=True)
class RangeFrequency:
    label: str
    size: int
    selections: int
    draws_present: int
    observed_presence: float | None
    expected_presence: float
    observed_average: float | None
    expected_average: float


@dataclass(frozen=True)
class HighNumberStatistics:
    threshold: int
    counts: tuple[int, ...]
    expected_counts: tuple[float, ...]
    average: float | None
    expected_average: float
    at_least_one: float | None
    at_least_two: float | None


@dataclass(frozen=True)
class RangeStatistics:
    game_max: int
    draw_count: int
    ranges: tuple[RangeFrequency, ...]
    patterns: dict[tuple[int, ...], int]
    high_numbers: tuple[HighNumberStatistics, ...]


class RangeAnalyzer:
    def analyze_draw(self, numbers: tuple[int, ...], game_max: int) -> tuple[int, ...]:
        if len(numbers) != 6:
            raise ValueError("A draw requires six numbers")
        return range_pattern(numbers, game_max)

    def calculate_pattern_frequencies(self, draws: tuple[HistoricalDraw, ...], game_max: int) -> dict:
        return dict(Counter(self.analyze_draw(draw.numbers, game_max) for draw in draws))

    def expected_range_distribution(self, game_max: int) -> tuple[float, ...]:
        return tuple(6 * len(bucket) / game_max for bucket in number_ranges(game_max))

    def calculate_high_number_statistics(self, draws: tuple[HistoricalDraw, ...], game_max: int) -> tuple[HighNumberStatistics, ...]:
        result = []
        for threshold in (40, 50):
            if threshold > game_max:
                continue
            counts = Counter(sum(n >= threshold for n in draw.numbers) for draw in draws)
            size = game_max - threshold + 1
            result.append(HighNumberStatistics(threshold, tuple(counts[k] for k in range(7)),
                expected_count_distribution(game_max, size),
                sum(k * v for k, v in counts.items()) / len(draws) if draws else None,
                6 * size / game_max,
                sum(v for k, v in counts.items() if k >= 1) / len(draws) if draws else None,
                sum(v for k, v in counts.items() if k >= 2) / len(draws) if draws else None))
        return tuple(result)

    def calculate_range_statistics(self, draws: tuple[HistoricalDraw, ...], game_max: int) -> RangeStatistics:
        patterns = self.calculate_pattern_frequencies(draws, game_max)
        rows = []
        for index, bucket in enumerate(number_ranges(game_max)):
            selections = sum(p[index] * count for p, count in patterns.items())
            present = sum(count for p, count in patterns.items() if p[index])
            rows.append(RangeFrequency(f"{bucket.start}-{bucket.stop - 1}", len(bucket), selections,
                present, present / len(draws) if draws else None,
                1 - expected_count_distribution(game_max, len(bucket))[0],
                selections / len(draws) if draws else None, 6 * len(bucket) / game_max))
        return RangeStatistics(game_max, len(draws), tuple(rows), patterns,
            self.calculate_high_number_statistics(draws, game_max))
