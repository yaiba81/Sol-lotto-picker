from collections import Counter
from dataclasses import replace
from datetime import date, timedelta

import pytest

from lotto_lab.analytics.engine import AnalyticsEngine
from lotto_lab.analytics.range_analyzer import range_pattern, uniform_patterns
from lotto_lab.domain import GameCode, HistoricalDraw
from lotto_lab.generator.engine import seeded_generator
from lotto_lab.strategy.config import BUILT_IN_STRATEGIES, JONATHAN_RANGE_CONFIG, StrategyConfig
from lotto_lab.strategy.range_weighting import StructuralWeights


def history(maximum=58):
    game = GameCode(f"6/{maximum}")
    values = (1,12,24,40,41,maximum)
    draws = tuple(HistoricalDraw(game, date(2024,1,1) + timedelta(days=i), values) for i in range(30))
    return AnalyticsEngine().analyze(game_code=game, maximum_number=maximum, game_draws=draws, cross_game_draws=draws)


def test_disabled_and_zero_strength_preserve_seeded_original_numbers_and_weights():
    snapshot = history()
    original = BUILT_IN_STRATEGIES["Jonathan Weighted v1"]
    for config in (replace(JONATHAN_RANGE_CONFIG, use_range=False, use_high_number_balance=False),
                   replace(JONATHAN_RANGE_CONFIG, range_strength=0)):
        a, b = seeded_generator(15), seeded_generator(15)
        for _ in range(8):
            left = a.generate(snapshot=snapshot, config=original, strategy_label="Original")
            right = b.generate(snapshot=snapshot, config=config, strategy_label="Enhanced")
            assert left.numbers == right.numbers
            assert [e.final_weight for e in left.selected_evaluations] == pytest.approx([e.final_weight for e in right.selected_evaluations])


@pytest.mark.parametrize("maximum", [42,45,49,55,58])
def test_all_games_valid_and_positive_with_maximum_strength(maximum):
    snapshot = history(maximum)
    engine = seeded_generator(81)
    config = replace(JONATHAN_RANGE_CONFIG, range_strength=1)
    for _ in range(12):
        ticket = engine.generate(snapshot=snapshot, config=config, strategy_label="Range experiment")
        assert len(set(ticket.numbers)) == 6
        assert all(1 <= n <= maximum for n in ticket.numbers)
        assert all(e.final_weight > 0 for e in ticket.selected_evaluations)
        if maximum < 55:
            assert all(e.factors["high_number_balance"] == pytest.approx(1) for e in ticket.selected_evaluations)


def test_structural_factor_changes_with_partial_and_is_not_blanket_high_bonus():
    snapshot = history()
    engine = seeded_generator(3)
    config = StrategyConfig(use_high_number_balance=True)
    wanted = engine.evaluate_candidate(55, (1,12,24,40,41), snapshot, config)
    overloaded = engine.evaluate_candidate(55, (40,41,43,44,45), snapshot, config)
    same_structure = engine.evaluate_candidate(58, (1,12,24,40,41), snapshot, config)
    assert wanted.factors["high_number_balance"] > overloaded.factors["high_number_balance"]
    assert wanted.factors["high_number_balance"] == same_structure.factors["high_number_balance"]


def test_every_pattern_including_unseen_has_positive_bounded_terminal_preference():
    snapshot = history()
    config = replace(JONATHAN_RANGE_CONFIG, range_strength=1)
    model = StructuralWeights(snapshot.range_statistics, config)
    for pattern, probability in uniform_patterns(58):
        assert probability > 0
        assert all(0.5 <= value <= 1.5 for value in model.potential(pattern))
    assert model.potential((6,0,0,0,0,0))[0] > 0


def test_sequential_sampling_has_exact_soft_pattern_distribution():
    snapshot = history()
    config = StrategyConfig(use_range=True, range_strength=1)
    model = StructuralWeights(snapshot.range_statistics, config)
    # Enumerate probabilities of partial compositions instead of a lucky sample.
    states = {(0,) * 6: 1.0}
    for step in range(6):
        next_states = Counter()
        for partial, probability in states.items():
            weights = []
            for index, size in enumerate(model.sizes):
                after = list(partial)
                after[index] += 1
                weights.append((tuple(after), (size - partial[index]) * model.factors(partial, tuple(after))[0]))
            total = sum(weight for _, weight in weights)
            for after, weight in weights:
                next_states[after] += probability * weight / total
        states = next_states
    root = model.potential((0,) * 6)[0]
    for pattern, baseline in uniform_patterns(58):
        assert states[pattern] == pytest.approx(baseline * model.potential(pattern)[0] / root)
    assert sum(states.values()) == pytest.approx(1)
    common = next(iter(snapshot.range_statistics.patterns))
    assert states[common] > dict(uniform_patterns(58))[common]


def test_weighted_generation_keeps_unseen_patterns_and_random_diversity():
    snapshot = history()
    engine = seeded_generator(92)
    patterns = Counter(range_pattern(engine.generate(snapshot=snapshot, config=JONATHAN_RANGE_CONFIG,
        strategy_label="Range").numbers, 58) for _ in range(150))
    assert len(patterns) > 20
    assert set(patterns) - snapshot.range_statistics.patterns.keys()


def test_legacy_json_defaults_disable_new_factors_and_validate_strength():
    config = StrategyConfig.from_json('{"use_bucket": true}')
    assert not config.use_range and not config.use_high_number_balance
    assert StrategyConfig.from_json(JONATHAN_RANGE_CONFIG.to_json()) == JONATHAN_RANGE_CONFIG
    for change in ({"range_strength": -0.1}, {"range_strength": 1.1}, {"structural_max_deviation": 1}, {"structural_prior_draws": 0}):
        with pytest.raises(ValueError):
            replace(config, **change)


def test_empty_history_neutral_and_model_replaced_for_new_snapshot():
    engine = seeded_generator(7)
    populated = history()
    engine.evaluate_candidate(55, (1,12,24,40,41), populated, JONATHAN_RANGE_CONFIG)
    empty = AnalyticsEngine().analyze(game_code=GameCode.ULTRA_LOTTO_6_58, maximum_number=58,
        game_draws=(), cross_game_draws=())
    evaluation = engine.evaluate_candidate(55, (1,12,24,40,41), empty, JONATHAN_RANGE_CONFIG)
    assert evaluation.factors["range"] == 1
    assert evaluation.factors["high_number_balance"] == 1
    assert evaluation.final_weight == seeded_generator(7).evaluate_candidate(
        55, (1,12,24,40,41), empty, JONATHAN_RANGE_CONFIG).final_weight
