from mma_secretary.core.draw import assign_control_numbers, first_fight_pairs, rank_strength, redraw_control_numbers
from mma_secretary.core.models import Participant


def P(i, **kw):
    base = dict(
        id=i,
        name=f"Боец {i}",
        organization="клуб",
        rank="",
        birth_year=2000,
        coach="",
        weight=70,
        status="взвешен",
        draw_number=i,
    )
    base.update(kw)
    return Participant(**base)


def test_stronger_gets_bye_when_possible():
    people = [
        P(1, rank="МС", organization="А"),
        P(2, rank="б/р", organization="Б"),
        P(3, rank="б/р", organization="В"),
        P(4, rank="", organization="Г"),
        P(5, rank="", organization="Д"),
    ]
    assigned = dict(assign_control_numbers(people))
    pairs = first_fight_pairs(5)
    fight_pos = {p for pair in pairs for p in pair}
    ms_pos = assigned[1]
    assert ms_pos not in fight_pos


def test_clubmates_not_in_first_fight():
    people = [
        P(1, organization="клетка", draw_number=1),
        P(2, organization="клетка", draw_number=2),
        P(3, organization="титан", draw_number=3),
        P(4, organization="витязь", draw_number=4),
    ]
    assigned = dict(assign_control_numbers(people))
    pos = {ctrl: pid for pid, ctrl in assigned.items()}
    by_id = {p.id: p for p in people}
    for a, b in first_fight_pairs(4):
        assert by_id[pos[a]].organization != by_id[pos[b]].organization


def test_redraw_uses_ranks():
    people = [P(1, rank="КМС"), P(2, rank=""), P(3, rank="МС")]
    assigned, seed = redraw_control_numbers(people, seed=1)
    assert seed == 1
    assert sorted(ctrl for _, ctrl in assigned) == [1, 2, 3]
    assert rank_strength("МС") > rank_strength("КМС") > rank_strength("")
