from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class CandidateEvaluation:
    number: int
    final_weight: float
    factors: dict[str, float]
    explanations: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class GeneratedCombination:
    numbers: tuple[int, ...]
    historical_pattern_score: float
    strategy_label: str
    selected_evaluations: tuple[CandidateEvaluation, ...]
    summary_factors: dict[str, float]

