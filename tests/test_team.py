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
