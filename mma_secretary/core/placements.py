from __future__ import annotations

from mma_secretary.core.bracket import loser_of
from mma_secretary.core.models import Bracket, Placement, PointRule, DEFAULT_POINT_RULES


ROUND_PLACE = {
    "финал": 2,
    "за бронзу": 4,
    "1/2": 3,
    "1/4": 5,
    "1/8": 9,
    "1/16": 17,
    "1/32": 33,
}


def placements_from_bracket(bracket: Bracket, *, two_bronzes: bool = True) -> list[Placement]:
    if bracket.kind == "empty" or bracket.n <= 0:
        return []
    return _elim_places(bracket, two_bronzes=two_bronzes)


def _elim_places(bracket: Bracket, *, two_bronzes: bool) -> list[Placement]:
    places: dict[int, int] = {}
    bronze = next((m for m in bracket.matches if m.round_code == "за бронзу"), None)
    final = next((m for m in bracket.matches if m.round_code == "финал"), None)
    if final and final.winner_ctrl is not None:
        places[final.winner_ctrl] = 1
        loser = loser_of(final)
        if loser is not None:
            places[loser] = 2

    if bronze and bronze.winner_ctrl is not None and not two_bronzes:
        places[bronze.winner_ctrl] = 3
        loser = loser_of(bronze)
        if loser is not None:
            places[loser] = 4
    else:
        for m in bracket.matches:
            if m.round_code == "1/2" and m.winner_ctrl is not None:
                loser = loser_of(m)
                if loser is not None:
                    places[loser] = 3

    for m in bracket.matches:
        if m.is_bye or m.winner_ctrl is None:
            continue
        loser = loser_of(m)
        if loser is None or loser in places:
            continue
        if m.round_code in {"финал", "за бронзу", "1/2"}:
            continue
        base = ROUND_PLACE.get(m.round_code)
        if base:
            places[loser] = base

    return [Placement(ctrl, place) for ctrl, place in sorted(places.items(), key=lambda x: (x[1], x[0]))]


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
