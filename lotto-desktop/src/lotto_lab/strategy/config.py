"""Typed, serializable configuration for Phase 4 built-in strategies."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
import math


@dataclass(frozen=True, slots=True)
class StrategyConfig:
    use_cross_game: bool = False
    use_sequence: bool = False
    use_bucket: bool = False
    use_odd_even: bool = False
    use_frequency: bool = False
    use_range: bool = False
    use_high_number_balance: bool = False
    range_strength: float = 0.20
    structural_max_deviation: float = 0.50
    structural_prior_draws: float = 20.0
    cross_game_penalty: float = 0.08
    sequence_pair_factor: float = 0.95
    sequence_three_factor: float = 0.65
    sequence_four_plus_factor: float = 0.35
    bucket_three_factor: float = 0.90
    bucket_four_factor: float = 0.55
    bucket_five_factor: float = 0.30
    bucket_six_factor: float = 0.20
    frequency_strength: float = 0.25
    minimum_factor: float = 0.10

    def __post_init__(self) -> None:
        for name, value in asdict(self).items():
            if name.startswith("use_"):
                if type(value) is not bool:
                    raise ValueError(f"{name} must be a boolean")
            elif type(value) not in (int, float) or not math.isfinite(value):
                raise ValueError(f"{name} must be a finite number")
        factors = (
            self.sequence_pair_factor,
            self.sequence_three_factor,
            self.sequence_four_plus_factor,
            self.bucket_three_factor,
            self.bucket_four_factor,
            self.bucket_five_factor,
            self.bucket_six_factor,
            self.minimum_factor,
        )
        if any(not 0 < value <= 1 for value in factors):
            raise ValueError("Soft-weight factors must be greater than 0 and at most 1")
        if not 0 <= self.cross_game_penalty <= 1:
            raise ValueError("Cross-game penalty must be between 0 and 1")
        if not 0 <= self.frequency_strength <= 1:
            raise ValueError("Frequency strength must be between 0 and 1")
        if not 0 <= self.range_strength <= 1:
            raise ValueError("Range strength must be between 0 and 1")
        if not 0 < self.structural_max_deviation <= 0.5:
            raise ValueError("Structural maximum deviation must be in (0, 0.5]")
        if not 0 < self.structural_prior_draws <= 10000:
            raise ValueError("Structural prior draws must be in (0, 10000]")

    def to_json(self) -> str:
        return json.dumps(asdict(self), sort_keys=True)

    @classmethod
    def from_json(cls, value: str) -> "StrategyConfig":
        return cls(**json.loads(value))


BUILT_IN_STRATEGIES: dict[str, StrategyConfig] = {
    "Pure Random v1": StrategyConfig(),
    "Jonathan Weighted v1": StrategyConfig(
        use_cross_game=True,
        use_sequence=True,
        use_bucket=True,
        use_odd_even=True,
    ),
    "Cross-Game Only v1": StrategyConfig(use_cross_game=True),
    "Bucket + Sequence v1": StrategyConfig(use_sequence=True, use_bucket=True),
    "Historical Frequency v1": StrategyConfig(use_frequency=True),
    "Hybrid v1": StrategyConfig(
        use_cross_game=True,
        use_sequence=True,
        use_bucket=True,
        use_odd_even=True,
        use_frequency=True,
        frequency_strength=0.15,
    ),
}

# Seeded as the next available version of the existing Jonathan family.
JONATHAN_RANGE_CONFIG = StrategyConfig(
    use_cross_game=True, use_sequence=True, use_bucket=True, use_odd_even=True,
    use_range=True, use_high_number_balance=True,
)
