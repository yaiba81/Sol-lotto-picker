from lotto_lab.domain import NUMBER_GROUPS, SUPPORTED_GAMES


def test_supported_games_match_pcso_ranges() -> None:
    assert [game.maximum_number for game in SUPPORTED_GAMES] == [42, 45, 49, 55, 58]
    assert all(game.picks == 6 for game in SUPPORTED_GAMES)


def test_number_groups_have_required_boundaries() -> None:
    assert [(group.start, group.stop - 1) for group in NUMBER_GROUPS] == [
        (1, 10), (11, 19), (20, 29), (30, 39), (40, 49), (50, 58)
    ]

