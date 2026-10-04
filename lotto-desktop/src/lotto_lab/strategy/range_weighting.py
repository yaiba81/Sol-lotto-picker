"""Bounded structural preferences integrated over uniform random completions.

No target pattern is mandatory. A terminal preference is 1 + strength * cap *
(observed - expected)/(observed + expected), shrunk toward neutral for small
samples. Step factors are ratios of expected terminal preferences after/before
the candidate. Under otherwise uniform sampling these telescope to a bounded
tilt of the uniform combination distribution, with full support.
"""
from collections import defaultdict

from lotto_lab.analytics.range_analyzer import RangeStatistics, uniform_patterns
from lotto_lab.strategy.config import StrategyConfig


class StructuralWeights:
    def __init__(self, statistics: RangeStatistics, config: StrategyConfig):
        self.sizes = tuple(row.size for row in statistics.ranges)
        self.maximum = statistics.game_max
        self.config = config
        self.active = (config.use_range and bool(statistics.draw_count) and config.range_strength > 0,
            config.use_high_number_balance and self.maximum >= 55 and bool(statistics.draw_count) and config.range_strength > 0)
        self.cache: dict[tuple[int, ...], tuple[float, float]] = {}
        expected = dict(uniform_patterns(self.maximum))
        high_expected: dict[tuple[int, int], float] = defaultdict(float)
        high_observed: dict[tuple[int, int], int] = defaultdict(int)
        for p, probability in expected.items():
            high_expected[self.high_key(p)] += probability
        for p, count in statistics.patterns.items():
            high_observed[self.high_key(p)] += count
        count = statistics.draw_count
        amplitude = config.range_strength * config.structural_max_deviation
        shrink = count / (count + config.structural_prior_draws)
        def preference(observed, probability):
            expected_count = count * probability
            deviation = ((observed - expected_count) / (observed + expected_count)
                         if observed + expected_count else 0.0)
            return 1 + amplitude * shrink * deviation
        for p, probability in expected.items():
            key = self.high_key(p)
            self.cache[p] = (
                preference(statistics.patterns.get(p, 0), probability) if config.use_range else 1.0,
                preference(high_observed[key], high_expected[key])
                if config.use_high_number_balance and self.maximum >= 55 else 1.0,
            )

    @staticmethod
    def high_key(pattern: tuple[int, ...]) -> tuple[int, int]:
        return sum(pattern[4:]), pattern[5] if len(pattern) > 5 else 0

    def potential(self, partial: tuple[int, ...]) -> tuple[float, float]:
        if partial not in self.cache:
            remaining = self.maximum - sum(partial)
            values = [0.0, 0.0]
            for index, size in enumerate(self.sizes):
                available = size - partial[index]
                if available:
                    proposed = list(partial)
                    proposed[index] += 1
                    child = self.potential(tuple(proposed))
                    for factor in range(2):
                        values[factor] += available / remaining * child[factor]
            self.cache[partial] = tuple(value if self.active[i] else 1.0 for i, value in enumerate(values))
        return self.cache[partial]

    def factors(self, before: tuple[int, ...], after: tuple[int, ...]) -> tuple[float, float]:
        return tuple(a / b for a, b in zip(self.potential(after), self.potential(before)))
