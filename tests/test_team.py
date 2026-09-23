from mma_secretary.core.team import team_standings


def test_sum_and_shared_place():
    rows = [
        ("клетка", 10, "65,8", 1),
        ("клетка", 2, "70,3", 5),
        ("Славянин", 12, "77,1", 1),
        ("Титан", 8, "70,3", 2),
    ]
    standings = team_standings(rows)
    by = {s.organization: s for s in standings}
    assert by["клетка"].points == 12
    assert by["Славянин"].points == 12
    assert by["клетка"].place == 1
    assert by["Славянин"].place == 1
    assert by["Титан"].place == 3


def test_more_first_places_wins_tie():
    rows = [
        ("альфа", 10, "65,8", 1),
        ("альфа", 2, "70,3", 5),
        ("бета", 8, "77,1", 2),
        ("бета", 2, "83,9", 5),
        ("бета", 2, "93", 5),
    ]
    standings = team_standings(rows)
    by = {s.organization: s for s in standings}
    assert by["альфа"].points == 12
    assert by["бета"].points == 12
    assert by["альфа"].place == 1
    assert by["бета"].place == 2
