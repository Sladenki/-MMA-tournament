from __future__ import annotations

import secrets
from collections.abc import Sequence

from mma_secretary.core.bracket import first_round_order
from mma_secretary.core.models import Participant
from mma_secretary.core.normalize import normalize_org, normalize_rank


RANK_STRENGTH = {
    "ЗМС": 100,
    "МСМК": 90,
    "МС": 80,
    "КМС": 70,
    "1": 60,
    "1 РАЗРЯД": 60,
    "I": 60,
    "2": 50,
    "2 РАЗРЯД": 50,
    "II": 50,
    "3": 40,
    "3 РАЗРЯД": 40,
    "III": 40,
    "Ю1": 30,
    "ЮНОШЕСКИЙ 1": 30,
    "Ю2": 20,
    "ЮНОШЕСКИЙ 2": 20,
    "Ю3": 10,
    "ЮНОШЕСКИЙ 3": 10,
    "Б/Р": 0,
    "БР": 0,
    "БЕЗ РАЗРЯДА": 0,
    "": 0,
}


def rank_strength(rank: str | None) -> int:
    r = normalize_rank(rank)
    if r in RANK_STRENGTH:
        return RANK_STRENGTH[r]
    if r.startswith("Ю"):
        return 25
    return 0


def first_fight_pairs(n: int) -> list[tuple[int, int]]:
    """Пары первого настоящего боя по контрольным номерам."""
    slots = first_round_order(n)
    pairs = [(s.a, s.b) for s in slots if s.kind == "fight" and s.b]
    if pairs:
        return pairs
    ctrls = [s.a for s in slots if s.kind == "bye" and s.a]
    return [(ctrls[i], ctrls[i + 1]) for i in range(0, len(ctrls) - 1, 2)]


def _same_club(a: Participant, b: Participant) -> bool:
    left, right = normalize_org(a.organization), normalize_org(b.organization)
    if not left or not right:
        return False
    return left.casefold() == right.casefold()


def assign_control_numbers(participants: Sequence[Participant]) -> list[tuple[int, int]]:
    """Жребий по разрядам, одноклубников в первом круге разводим.

    Если номера жребия уже есть — они решают порядок внутри одного разряда.
    """
    return _place_people(list(participants), rng=None)


def redraw_control_numbers(
    people: Sequence[Participant],
    *,
    seed: int | None = None,
) -> tuple[list[tuple[int, int]], int]:
    """Новый жребий: сильнее по разряду дальше друг от друга, клубы разводим."""
    if seed is None:
        seed = secrets.randbits(32)
    return _place_people(list(people), rng=_rng(seed)), seed


def _place_people(people: list[Participant], rng) -> list[tuple[int, int]]:
    n = len(people)
    if n == 0:
        return []
    if n == 1:
        return [(people[0].id, 1)]

    ordered = list(people)
    if rng is not None:
        _shuffle(ordered, rng)
        ordered.sort(key=lambda p: -rank_strength(p.rank))
    else:
        ordered.sort(
            key=lambda p: (
                -rank_strength(p.rank),
                p.draw_number is None,
                p.draw_number if p.draw_number is not None else 10**9,
                p.name.casefold(),
                p.id,
            )
        )

    pairs = first_fight_pairs(n)
    opp = {}
    for a, b in pairs:
        opp[a] = b
        opp[b] = a
    bye_pos = {i for i in range(1, n + 1) if i not in opp}

    pos_of: dict[int, Participant | None] = {i: None for i in range(1, n + 1)}
    taken: set[int] = set()

    def clash(person: Participant, pos: int) -> bool:
        other_pos = opp.get(pos)
        if other_pos is None or other_pos not in taken:
            return False
        other = pos_of[other_pos]
        return bool(other and _same_club(person, other))

    placed_ids: set[int] = set()
    for person in ordered:
        free = [p for p in range(1, n + 1) if p not in taken]
        good = [p for p in free if not clash(person, p)]
        pool = good or free
        my = rank_strength(person.rank)
        prefer_bye = any(rank_strength(p.rank) < my for p in people if p.id not in placed_ids)

        def score(pos: int) -> tuple:
            if prefer_bye:
                return (0 if pos in bye_pos else 1, 0 if not clash(person, pos) else 1, pos)
            return (0 if not clash(person, pos) else 1, pos)

        pos = min(pool, key=score)
        pos_of[pos] = person
        taken.add(pos)
        placed_ids.add(person.id)

    _repair_clubs(pos_of, pairs)
    return [(pos_of[i].id, i) for i in range(1, n + 1) if pos_of[i] is not None]


def _repair_clubs(pos_of: dict[int, Participant | None], pairs: list[tuple[int, int]]) -> None:
    opp = {}
    for a, b in pairs:
        opp[a] = b
        opp[b] = a

    for a, b in pairs:
        pa, pb = pos_of.get(a), pos_of.get(b)
        if not pa or not pb or not _same_club(pa, pb):
            continue
        for c, pc in pos_of.items():
            if c in (a, b) or pc is None:
                continue
            other_c = opp.get(c)
            other_person = pos_of.get(other_c) if other_c else None
            if other_person and _same_club(pa, other_person):
                continue
            if other_person and _same_club(pb, other_person):
                continue
            pos_of[b], pos_of[c] = pos_of[c], pos_of[b]
            break


def _rng(seed: int):
    import random

    return random.Random(seed)


def _shuffle(items: list, rng) -> None:
    for i in range(len(items) - 1, 0, -1):
        j = rng.randrange(i + 1)
        items[i], items[j] = items[j], items[i]
