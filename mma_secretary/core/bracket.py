from __future__ import annotations

from mma_secretary.core.models import Bracket, FirstRoundSlot, MatchSpec


ROUND_BY_SLOTS = {
    64: "1/32",
    32: "1/16",
    16: "1/8",
    8: "1/8",
    4: "1/4",
    2: "1/2",
    1: "финал",
}


def bracket_size(n: int) -> int:
    if n <= 0:
        return 0
    if n == 1:
        return 1
    if n == 2:
        return 2
    if n == 3:
        return 3
    if n <= 8:
        return 8
    if n <= 16:
        return 16
    if n <= 32:
        return 32
    if n <= 64:
        return 64
    raise ValueError("В категории больше 64 участников: сетка не строится")


def first_round_order(n: int) -> list[FirstRoundSlot]:
    if n <= 0:
        return []
    if n == 1:
        return [FirstRoundSlot("bye", 1)]
    if n == 2:
        return [FirstRoundSlot("fight", 1, 2)]
    if n == 3:
        return [
            FirstRoundSlot("fight", 1, 2),
            FirstRoundSlot("fight", 1, 3),
            FirstRoundSlot("fight", 2, 3),
        ]
    size = bracket_size(n)
    byes = size - n
    pairs = (n - byes) // 2
    order: list[FirstRoundSlot] = []
    num = 1
    for _ in range(pairs):
        order.append(FirstRoundSlot("fight", num, num + 1))
        num += 2
        if byes:
            order.append(FirstRoundSlot("bye", num))
            num += 1
            byes -= 1
    while byes:
        order.append(FirstRoundSlot("bye", num))
        num += 1
        byes -= 1
    return order


def _round_name(slot_count: int, is_last: bool) -> str:
    if is_last:
        return "финал"
    return {
        32: "1/32",
        16: "1/16",
        8: "1/8",
        4: "1/4",
        2: "1/2",
        1: "финал",
    }.get(slot_count, f"t{slot_count}")


def build_bracket(n: int, *, bronze_bout: bool = False) -> Bracket:
    if n < 0:
        raise ValueError("n < 0")
    if n > 64:
        raise ValueError("В категории больше 64 участников: сетка не строится")
    if n == 0:
        return Bracket(0, 0, "empty")
    if n == 1:
        match = MatchSpec(
            key="auto-1",
            round_code="без боя",
            slot=0,
            blue_ctrl=1,
            winner_ctrl=1,
            is_bye=True,
        )
        return Bracket(1, 1, "walkover", [FirstRoundSlot("bye", 1)], [match])
    if n == 2:
        match = MatchSpec(key="F", round_code="финал", slot=0, blue_ctrl=1, red_ctrl=2)
        return Bracket(2, 2, "final", [FirstRoundSlot("fight", 1, 2)], [match])
    if n == 3:
        matches = [
            MatchSpec(key="RR-1", round_code="круг", slot=0, blue_ctrl=1, red_ctrl=2),
            MatchSpec(key="RR-2", round_code="круг", slot=1, blue_ctrl=1, red_ctrl=3),
            MatchSpec(key="RR-3", round_code="круг", slot=2, blue_ctrl=2, red_ctrl=3),
        ]
        return Bracket(3, 3, "round_robin", first_round_order(3), matches)

    first = first_round_order(n)
    matches: list[MatchSpec] = []
    current: list[MatchSpec] = []
    for i, slot in enumerate(first):
        if slot.kind == "bye":
            m = MatchSpec(
                key=f"R1-{i}",
                round_code=_round_name(len(first), False),
                slot=i,
                blue_ctrl=slot.a,
                winner_ctrl=slot.a,
                is_bye=True,
            )
        else:
            m = MatchSpec(
                key=f"R1-{i}",
                round_code=_round_name(len(first), False),
                slot=i,
                blue_ctrl=slot.a,
                red_ctrl=slot.b,
            )
        current.append(m)
        matches.append(m)

    rnd = 2
    while len(current) > 1:
        nxt: list[MatchSpec] = []
        is_last = len(current) == 2
        code = _round_name(len(current) // 2, is_last) if not is_last else "финал"
        # winners of adjacent slots meet
        for i in range(0, len(current), 2):
            left, right = current[i], current[i + 1]
            m = MatchSpec(
                key=f"R{rnd}-{i // 2}",
                round_code=code,
                slot=i // 2,
                source_blue=left.key,
                source_red=right.key,
            )
            nxt.append(m)
            matches.append(m)
        current = nxt
        rnd += 1

    if bronze_bout and n >= 4:
        semis = [m for m in matches if m.round_code == "1/2"]
        if len(semis) == 2:
            matches.append(
                MatchSpec(
                    key="BRONZE",
                    round_code="за бронзу",
                    slot=0,
                    source_blue=semis[0].key,
                    source_red=semis[1].key,
                )
            )

    bracket = Bracket(n, bracket_size(n), "single_elim", first, matches)
    _propagate(bracket)
    return bracket


def apply_winner(bracket: Bracket, match_key: str, winner_ctrl: int) -> Bracket:
    """Проставить победителя и продвинуть его в следующий тур. Исправление сбрасывает дальше."""
    by_key = {m.key: m for m in bracket.matches}
    if match_key not in by_key:
        raise KeyError(match_key)
    match = by_key[match_key]
    if match.is_bye:
        raise ValueError("Нельзя править проход")
    allowed = {match.blue_ctrl, match.red_ctrl}
    if None in allowed:
        raise ValueError("Оба участника ещё не определены")
    if winner_ctrl not in allowed:
        raise ValueError("Победитель должен быть одним из участников боя")
    match.winner_ctrl = winner_ctrl
    _propagate(bracket)
    return bracket


def clear_result(bracket: Bracket, match_key: str) -> Bracket:
    by_key = {m.key: m for m in bracket.matches}
    if match_key not in by_key:
        raise KeyError(match_key)
    match = by_key[match_key]
    if match.is_bye:
        return bracket
    match.winner_ctrl = None
    _propagate(bracket)
    return bracket


def _propagate(bracket: Bracket) -> None:
    by_key = {m.key: m for m in bracket.matches}
    for m in bracket.matches:
        if m.is_bye:
            continue
        if m.source_blue:
            src = by_key[m.source_blue]
            if m.round_code == "за бронзу":
                m.blue_ctrl = _loser(src)
            else:
                m.blue_ctrl = src.winner_ctrl
        if m.source_red:
            src = by_key[m.source_red]
            if m.round_code == "за бронзу":
                m.red_ctrl = _loser(src)
            else:
                m.red_ctrl = src.winner_ctrl
        if m.winner_ctrl is not None and m.winner_ctrl not in {m.blue_ctrl, m.red_ctrl}:
            m.winner_ctrl = None


def _loser(match: MatchSpec) -> int | None:
    if match.winner_ctrl is None or match.blue_ctrl is None or match.red_ctrl is None:
        return None
    return match.red_ctrl if match.winner_ctrl == match.blue_ctrl else match.blue_ctrl


def fight_count(n: int, bronze_bout: bool = False) -> int:
    if n <= 1:
        return 0
    if n == 2:
        return 1
    if n == 3:
        return 3
    extra = 1 if bronze_bout and n >= 4 else 0
    return n - 1 + extra
