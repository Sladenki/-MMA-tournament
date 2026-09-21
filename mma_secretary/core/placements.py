from __future__ import annotations

from collections import defaultdict

from mma_secretary.core.models import Bracket, MatchSpec, Placement, PointRule, DEFAULT_POINT_RULES


ROUND_PLACE = {
    "финал": 2,  # loser of final is 2nd; winner handled separately
    "за бронзу": 4,
    "1/2": 3,
    "1/4": 5,
    "1/8": 9,
    "1/16": 17,
    "1/32": 33,
    "круг": None,
}


def placements_from_bracket(bracket: Bracket, *, two_bronzes: bool = True) -> list[Placement]:
    if bracket.kind == "empty":
        return []
    if bracket.kind == "walkover":
        return [Placement(1, 1)]
    if bracket.kind == "round_robin":
        return _round_robin_places(bracket.matches)
    return _elim_places(bracket, two_bronzes=two_bronzes)


def _loser(match: MatchSpec) -> int | None:
    if match.winner_ctrl is None or match.blue_ctrl is None or match.red_ctrl is None:
        return None
    return match.red_ctrl if match.winner_ctrl == match.blue_ctrl else match.blue_ctrl


def _elim_places(bracket: Bracket, *, two_bronzes: bool) -> list[Placement]:
    places: dict[int, int] = {}
    bronze = next((m for m in bracket.matches if m.round_code == "за бронзу"), None)
    final = next((m for m in bracket.matches if m.round_code == "финал" and not m.is_bye), None)
    if final and final.winner_ctrl is not None:
        places[final.winner_ctrl] = 1
        loser = _loser(final)
        if loser is not None:
            places[loser] = 2

    if bronze and bronze.winner_ctrl is not None and not two_bronzes:
        places[bronze.winner_ctrl] = 3
        loser = _loser(bronze)
        if loser is not None:
            places[loser] = 4
    else:
        for m in bracket.matches:
            if m.round_code == "1/2" and m.winner_ctrl is not None:
                loser = _loser(m)
                if loser is not None:
                    places[loser] = 3

    for m in bracket.matches:
        if m.is_bye or m.winner_ctrl is None:
            continue
        loser = _loser(m)
        if loser is None or loser in places:
            continue
        if m.round_code in {"финал", "за бронзу", "1/2"}:
            continue
        base = ROUND_PLACE.get(m.round_code)
        if base:
            places[loser] = base

    return [Placement(ctrl, place) for ctrl, place in sorted(places.items(), key=lambda x: (x[1], x[0]))]


def _round_robin_places(matches: list[MatchSpec]) -> list[Placement]:
    wins: dict[int, int] = defaultdict(int)
    seen: set[int] = set()
    h2h: dict[tuple[int, int], int] = {}
    for m in matches:
        if m.blue_ctrl:
            seen.add(m.blue_ctrl)
        if m.red_ctrl:
            seen.add(m.red_ctrl)
        if m.winner_ctrl is None or m.blue_ctrl is None or m.red_ctrl is None:
            continue
        wins[m.winner_ctrl] += 1
        loser = m.red_ctrl if m.winner_ctrl == m.blue_ctrl else m.blue_ctrl
        h2h[(m.winner_ctrl, loser)] = 1
        wins.setdefault(loser, 0)

    if not seen:
        return []
    if any(m.winner_ctrl is None and not m.is_bye for m in matches):
        # частичные результаты: места только тем, у кого все бои сыграны? нет — считаем по имеющимся победам
        pass

    def better(a: int, b: int) -> int:
        if wins[a] != wins[b]:
            return 1 if wins[a] > wins[b] else -1
        if (a, b) in h2h:
            return 1
        if (b, a) in h2h:
            return -1
        return 0

    ordered = sorted(seen, key=lambda c: (-wins.get(c, 0), c))
    result: list[Placement] = []
    i = 0
    place = 1
    while i < len(ordered):
        j = i + 1
        while j < len(ordered) and better(ordered[i], ordered[j]) == 0 and better(ordered[j], ordered[i]) == 0:
            j += 1
        tied = (j - i) > 1
        for k in range(i, j):
            result.append(Placement(ordered[k], place, tied=tied))
        place += j - i
        i = j
    return result


def points_for(place: int, rules: list[PointRule] | tuple[PointRule, ...] = DEFAULT_POINT_RULES) -> int:
    for rule in rules:
        if rule.place_from <= place <= rule.place_to:
            return rule.points
    return 0


def apply_points(
    placements: list[Placement],
    rules: list[PointRule] | tuple[PointRule, ...] = DEFAULT_POINT_RULES,
) -> list[tuple[Placement, int]]:
    return [(p, points_for(p.place, rules)) for p in placements]
