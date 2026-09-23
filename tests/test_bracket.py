import pytest

from mma_secretary.core.bracket import apply_winner, bracket_size, build_bracket, fight_count, first_round_order
from mma_secretary.core.placements import placements_from_bracket


def ctrls(order):
    out = []
    for s in order:
        if s.kind == "fight":
            out.append(("бой", s.a, s.b))
        else:
            out.append(("проход", s.a))
    return out


def test_size_table():
    assert [bracket_size(n) for n in (0, 1, 2, 3, 4, 8, 9, 16, 17, 32, 33, 64)] == [
        0, 1, 2, 4, 8, 8, 16, 16, 32, 32, 64, 64,
    ]


def test_n_over_64_errors():
    with pytest.raises(ValueError):
        build_bracket(65)


def test_first_round_n5():
    assert ctrls(first_round_order(5)) == [("бой", 1, 2), ("проход", 3), ("проход", 4), ("проход", 5)]


def test_first_round_n6():
    assert ctrls(first_round_order(6)) == [("бой", 1, 2), ("проход", 3), ("бой", 4, 5), ("проход", 6)]


def test_fight_count_invariants():
    for n in range(0, 65):
        b = build_bracket(n, bronze_bout=False)
        real = [m for m in b.matches if not m.is_bye]
        assert len(real) == fight_count(n, bronze_bout=False)
        if n >= 2:
            assert len(real) == n - 1


def test_n3_olympic_not_round_robin():
    b = build_bracket(3)
    assert b.kind == "single_elim"
    assert b.size == 4
    real = [m for m in b.matches if not m.is_bye]
    assert len(real) == 2
    fight = next(m for m in b.matches if m.round_code == "1/2" and not m.is_bye)
    apply_winner(b, fight.key, fight.blue_ctrl)
    final = next(m for m in b.matches if m.round_code == "финал")
    assert {final.blue_ctrl, final.red_ctrl} == {fight.blue_ctrl, 3}
    apply_winner(b, final.key, final.blue_ctrl)
    places = {p.control_number: p.place for p in placements_from_bracket(b)}
    assert sorted(places.values()) == [1, 2, 3]


def test_no_bye_vs_bye_in_first_fight_slots():
    for n in range(4, 65):
        for s in first_round_order(n):
            if s.kind == "fight":
                assert s.a and s.b


def test_advance_and_places():
    b = build_bracket(4)
    # n=4: четыре прохода, сразу 1/2. Соседи: 1–2 и 3–4.
    semis = [m for m in b.matches if m.round_code == "1/2"]
    assert len(semis) == 2
    assert {semis[0].blue_ctrl, semis[0].red_ctrl} == {1, 2}
    assert {semis[1].blue_ctrl, semis[1].red_ctrl} == {3, 4}
    apply_winner(b, semis[0].key, semis[0].blue_ctrl)
    apply_winner(b, semis[1].key, semis[1].blue_ctrl)
    final = next(m for m in b.matches if m.round_code == "финал")
    assert {final.blue_ctrl, final.red_ctrl} == {semis[0].blue_ctrl, semis[1].blue_ctrl}
    apply_winner(b, final.key, final.blue_ctrl)
    places = {p.control_number: p.place for p in placements_from_bracket(b)}
    assert places[final.winner_ctrl] == 1
    assert 2 in places.values()
    assert list(places.values()).count(3) == 2


def test_cannot_score_before_both_known():
    b = build_bracket(5)
    final = next(m for m in b.matches if m.round_code == "финал")
    with pytest.raises(ValueError):
        apply_winner(b, final.key, 1)
