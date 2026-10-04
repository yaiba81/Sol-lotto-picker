"""Explainable dynamic weighted-random selection without replacement."""

from __future__ import annotations

import math
import secrets
from collections import Counter
from random import Random
from typing import Protocol

from lotto_lab.analytics.engine import (
    AnalyticsSnapshot,
    maximum_group_concentration,
    odd_count,
    sequence_category,
)
from lotto_lab.domain import number_group_index
from lotto_lab.generator.models import CandidateEvaluation, GeneratedCombination
from lotto_lab.strategy.config import StrategyConfig
from lotto_lab.analytics.range_analyzer import range_pattern
from lotto_lab.strategy.range_weighting import StructuralWeights


class RandomSource(Protocol):
    def random(self) -> float: ...


FACTOR_NAMES = ("cross_game", "sequence", "bucket", "odd_even", "frequency", "range", "high_number_balance")


class WeightedGenerator:
    def __init__(self, random_source: RandomSource | None = None) -> None:
        self.random_source = random_source or secrets.SystemRandom()
        self._structural_context = None
        self._structural_model = None

    def generate(
        self,
        *,
        snapshot: AnalyticsSnapshot,
        config: StrategyConfig,
        strategy_label: str,
    ) -> GeneratedCombination:
        selected: list[int] = []
        selected_evaluations: list[CandidateEvaluation] = []

        while len(selected) < 6:
            evaluations = [
                self.evaluate_candidate(number, tuple(selected), snapshot, config)
                for number in range(1, snapshot.maximum_number + 1)
                if number not in selected
            ]
            chosen = self._choose(evaluations)
            selected.append(chosen.number)
            selected_evaluations.append(chosen)

        numbers = tuple(sorted(selected))
        return GeneratedCombination(
            numbers=numbers,
            historical_pattern_score=self._pattern_score(numbers, snapshot),
            strategy_label=strategy_label,
            selected_evaluations=tuple(selected_evaluations),
            summary_factors=self._summary_factors(selected_evaluations),
        )

    def evaluate_candidate(
        self,
        number: int,
        partial: tuple[int, ...],
        snapshot: AnalyticsSnapshot,
        config: StrategyConfig,
    ) -> CandidateEvaluation:
        factors = {name: 1.0 for name in FACTOR_NAMES}
        explanations: list[str] = []
        proposed = partial + (number,)

        if config.use_cross_game:
            game_count = snapshot.cross_game_occurrences.get(number, 0)
            factors["cross_game"] = max(
                config.minimum_factor, 1.0 - config.cross_game_penalty * max(0, game_count - 1)
            )
            explanations.append(f"Present in {game_count} game window(s)")

        if config.use_sequence:
            category = sequence_category(proposed)
            factors["sequence"] = {
                "none": 1.0,
                "2": config.sequence_pair_factor,
                "3": config.sequence_three_factor,
                "4+": config.sequence_four_plus_factor,
            }[category]
            explanations.append(f"Creates consecutive category: {category}")

        if config.use_bucket:
            concentration = Counter(number_group_index(value) for value in proposed)[
                number_group_index(number)
            ]
            factors["bucket"] = {
                1: 1.0,
                2: 1.0,
                3: config.bucket_three_factor,
                4: config.bucket_four_factor,
                5: config.bucket_five_factor,
                6: config.bucket_six_factor,
            }[concentration]
            explanations.append(f"Would place {concentration} selected number(s) in its group")

        if config.use_odd_even:
            factors["odd_even"] = self._parity_factor(proposed, snapshot, config.minimum_factor)
            explanations.append(
                f"Leaves {odd_count(proposed)} odd and {len(proposed) - odd_count(proposed)} even so far"
            )

        if config.use_frequency:
            factors["frequency"] = self._frequency_factor(number, snapshot, config)
            explanations.append(
                f"Appeared {snapshot.number_frequencies.get(number, 0)} time(s) in selected-game history"
            )

        if (config.use_range or config.use_high_number_balance) and config.range_strength > 0 and snapshot.range_statistics:
            # Retain only the current cutoff's model; never reuse it for a different snapshot.
            context = self._structural_context
            if context is None or context[0] is not snapshot or context[1] != config:
                self._structural_context = (snapshot, config)
                self._structural_model = StructuralWeights(snapshot.range_statistics, config)
            before = range_pattern(partial, snapshot.maximum_number)
            after = range_pattern(proposed, snapshot.maximum_number)
            factors["range"], factors["high_number_balance"] = self._structural_model.factors(before, after)
            explanations.append(
                f"Range composition {'-'.join(map(str, after))}; soft range factor {factors['range']:.4f}, "
                f"high-number structure factor {factors['high_number_balance']:.4f}; "
                "compared with uniform random composition, not individual number likelihood"
            )

        final_weight = math.prod(factors.values())
        if not explanations:
            explanations.append("Pure random: all candidates retain base weight 1.0")
        return CandidateEvaluation(number, final_weight, factors, tuple(explanations))

    def _choose(self, evaluations: list[CandidateEvaluation]) -> CandidateEvaluation:
        total = sum(item.final_weight for item in evaluations)
        if total <= 0:
            raise ValueError("At least one candidate must have a positive weight")
        threshold = self.random_source.random() * total
        cumulative = 0.0
        for item in evaluations:
            cumulative += item.final_weight
            if threshold < cumulative:
                return item
        return evaluations[-1]

    @staticmethod
    def _frequency_factor(
        number: int, snapshot: AnalyticsSnapshot, config: StrategyConfig
    ) -> float:
        if not snapshot.draw_count:
            return 1.0
        frequencies = snapshot.number_frequencies.values()
        mean = sum(frequencies) / snapshot.maximum_number
        if mean == 0:
            return 1.0
        relative = snapshot.number_frequencies.get(number, 0) / mean
        adjusted = 1.0 + config.frequency_strength * (relative - 1.0)
        return max(config.minimum_factor, adjusted)

    @staticmethod
    def _parity_factor(
        proposed: tuple[int, ...], snapshot: AnalyticsSnapshot, minimum: float
    ) -> float:
        if not snapshot.draw_count:
            return 1.0
        current_odds = odd_count(proposed)
        remaining = 6 - len(proposed)
        reachable = range(current_odds, current_odds + remaining + 1)
        smoothed = {
            count: snapshot.odd_even_distribution.get(count, 0) + 1 for count in range(7)
        }
        best = max(smoothed.values())
        expected = sum(smoothed[count] for count in reachable) / len(tuple(reachable))
        return max(minimum, expected / best)

    @staticmethod
    def _summary_factors(
        evaluations: list[CandidateEvaluation],
    ) -> dict[str, float]:
        return {
            name: round(
                math.prod(item.factors[name] for item in evaluations) ** (1 / len(evaluations)),
                4,
            )
            for name in FACTOR_NAMES
        }

    @staticmethod
    def _pattern_score(numbers: tuple[int, ...], snapshot: AnalyticsSnapshot) -> float:
        if not snapshot.draw_count:
            return 50.0

        def relative(distribution: dict, key: object) -> float:
            smoothed = {item: count + 1 for item, count in distribution.items()}
            return smoothed.get(key, 1) / max(smoothed.values())

        frequency_mean = sum(snapshot.number_frequencies[number] for number in numbers) / 6
        max_frequency = max(snapshot.number_frequencies.values(), default=0) or 1
        components = (
            min(1.0, frequency_mean / max_frequency),
            relative(snapshot.sequence_distribution, sequence_category(numbers)),
            relative(snapshot.bucket_distribution, maximum_group_concentration(numbers)),
            relative(snapshot.odd_even_distribution, odd_count(numbers)),
        )
        return round(100 * sum(components) / len(components), 1)


def seeded_generator(seed: int) -> WeightedGenerator:
    """Convenience factory reserved for repeatable tests and future backtests."""
    return WeightedGenerator(Random(seed))
