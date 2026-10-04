from lotto_lab.analytics.engine import AnalyticsSnapshot
from lotto_lab.domain import GameCode
from lotto_lab.generator.engine import seeded_generator
from lotto_lab.strategy.config import StrategyConfig


def snapshot() -> AnalyticsSnapshot:
    return AnalyticsSnapshot(
        game_code=GameCode.LOTTO_6_42,
        maximum_number=42,
        draw_count=10,
        number_frequencies={number: (10 if number == 1 else 1) for number in range(1, 43)},
        cross_game_occurrences={number: (5 if number == 14 else 1) for number in range(1, 43)},
        sequence_distribution={"none": 6, "2": 3, "3": 1, "4+": 0},
        bucket_distribution={1: 0, 2: 3, 3: 5, 4: 2, 5: 0, 6: 0},
        odd_even_distribution={0: 0, 1: 1, 2: 2, 3: 4, 4: 2, 5: 1, 6: 0},
    )


def test_pure_random_keeps_every_factor_at_one_and_no_replacement() -> None:
    result = seeded_generator(23).generate(
        snapshot=snapshot(), config=StrategyConfig(), strategy_label="Pure Random v1"
    )

    assert len(result.numbers) == len(set(result.numbers)) == 6
    assert all(1 <= number <= 42 for number in result.numbers)
    assert all(
        set(evaluation.factors.values()) == {1.0}
        for evaluation in result.selected_evaluations
    )


def test_candidate_weights_change_with_partial_ticket_and_remain_positive() -> None:
    generator = seeded_generator(1)
    config = StrategyConfig(use_cross_game=True, use_sequence=True, use_bucket=True)

    ordinary = generator.evaluate_candidate(14, (), snapshot(), config)
    creates_three_run = generator.evaluate_candidate(14, (12, 13), snapshot(), config)

    assert creates_three_run.factors["sequence"] < ordinary.factors["sequence"]
    assert creates_three_run.factors["bucket"] < ordinary.factors["bucket"]
    assert creates_three_run.factors["cross_game"] < 1.0
    assert creates_three_run.final_weight > 0


def test_frequency_strategy_increases_weight_for_more_frequent_number() -> None:
    generator = seeded_generator(1)
    config = StrategyConfig(use_frequency=True)

    frequent = generator.evaluate_candidate(1, (), snapshot(), config)
    ordinary = generator.evaluate_candidate(2, (), snapshot(), config)

    assert frequent.factors["frequency"] > ordinary.factors["frequency"]

