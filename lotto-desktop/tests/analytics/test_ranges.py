from datetime import date
from math import comb

import pytest

from lotto_lab.analytics.range_analyzer import RangeAnalyzer, number_ranges, range_pattern, uniform_patterns
from lotto_lab.domain import GameCode, HistoricalDraw


@pytest.mark.parametrize("maximum,sizes", [(42, (9,10,10,10,3)), (45, (9,10,10,10,6)),
    (49, (9,10,10,10,10)), (55, (9,10,10,10,10,6)), (58, (9,10,10,10,10,9))])
def test_ranges_partition_each_game(maximum, sizes):
    ranges = number_ranges(maximum)
    assert tuple(map(len, ranges)) == sizes
    assert [n for r in ranges for n in r] == list(range(1, maximum + 1))
    assert range_pattern((9,10,19,20,39,maximum), maximum) == (
        (1,2,1,1,1) if maximum < 50 else (1,2,1,1,0,1))
    assert sum(probability for _, probability in uniform_patterns(maximum)) == pytest.approx(1)
    assert sum(RangeAnalyzer().expected_range_distribution(maximum)) == pytest.approx(6)


def test_example_pattern_and_actual_statistics():
    draws = tuple(HistoricalDraw(GameCode.ULTRA_LOTTO_6_58, date(2025,1,day), numbers)
        for day, numbers in ((1, (12,24,36,43,47,55)), (2, (10,20,30,40,49,58)), (3, (1,2,3,4,5,6))))
    analyzer = RangeAnalyzer()
    assert analyzer.analyze_draw(draws[0].numbers, 58) == (0,1,1,1,2,1)
    stats = analyzer.calculate_range_statistics(draws, 58)
    assert stats.patterns == {(0,1,1,1,2,1): 2, (6,0,0,0,0,0): 1}
    assert stats.ranges[4].selections == 4
    assert stats.ranges[4].observed_presence == pytest.approx(2/3)
    assert stats.ranges[4].expected_presence == pytest.approx(1 - comb(48,6)/comb(58,6))
    assert stats.ranges[4].observed_average == pytest.approx(4/3)
    assert stats.ranges[4].expected_average == pytest.approx(60/58)
    high40, high50 = stats.high_numbers
    assert high40.counts == (1,0,0,2,0,0,0)
    assert high40.average == 2
    assert high40.at_least_one == high40.at_least_two == pytest.approx(2/3)
    assert high50.counts == (1,2,0,0,0,0,0)
    assert high50.average == pytest.approx(2/3)
    assert high50.expected_average == pytest.approx(54/58)
    assert sum(high40.expected_counts) == pytest.approx(1)


def test_no_history_is_missing_observation_not_zero_frequency():
    stats = RangeAnalyzer().calculate_range_statistics((), 42)
    assert stats.patterns == {}
    assert all(row.observed_average is None and row.observed_presence is None for row in stats.ranges)
    assert len(stats.high_numbers) == 1
    assert stats.high_numbers[0].average is None


@pytest.mark.parametrize("numbers", [(1,2,3,4,5), (1,1,2,3,4,5), (1,2,3,4,5,56), (1,2,3,4,5,0)])
def test_invalid_draw(numbers):
    with pytest.raises(ValueError):
        RangeAnalyzer().analyze_draw(numbers, 55)
