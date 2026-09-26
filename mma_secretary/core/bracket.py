from __future__ import annotations

from mma_secretary.core.models import Bracket, FirstRoundSlot, MatchSpec


def bracket_size(n: int) -> int:
    if n <= 0:
        return 0
    size = 4
    while size < n:
        size *= 2
        if size > 64:
            raise ValueError("В категории больше 64 участников: сетка не строится")
    return size


def _positions(n: int, size: int) -> list[int | None]:
    pos: list[int | None] = [None] * size
    if n <= 0 or size <= 0:
        return pos
    if n == 1:
        pos[0] = 1
        return pos
    if n == 2:
        pos[0] = 1
        pos[size // 2] = 2
        return pos
    if n == 3:
        pos[0], pos[1] = 1, 2
        pos[size // 2] = 3
        return pos
    byes = size - n
    pairs = (n - byes) // 2
    num = 1
    i = 0
    for _ in range(pairs):
        pos[i] = num
        pos[i + 1] = num + 1
        num += 2
        i += 2
        if byes:
            pos[i] = num
            num += 1
            i += 2
            byes -= 1
    while byes:
        pos[i] = num
        num += 1
        i += 2
        byes -= 1
    return pos


def first_round_order(n: int) -> list[FirstRoundSlot]:
    size = bracket_size(n)
    pos = _positions(n, size)
    order: list[FirstRoundSlot] = []
    for i in range(0, size, 2):
        a, b = pos[i], pos[i + 1] if i + 1 < size else None
        if a and b:
            order.append(FirstRoundSlot("fight", a, b))
        elif a:
            order.append(FirstRoundSlot("bye", a))
        elif b:
            order.append(FirstRoundSlot("bye", b))
        else:
            order.append(FirstRoundSlot("empty", 0))
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


def _source_can_produce(src: MatchSpec) -> bool:
    if src.winner_ctrl:
        return True
    if src.blue_ctrl or src.red_ctrl:
        return True
    return False


def _fill_bye(m: MatchSpec, by_key: dict[str, MatchSpec]) -> None:
    if m.winner_ctrl is not None:
        return
    blue_later = bool(m.source_blue and _source_can_produce(by_key[m.source_blue]))
    red_later = bool(m.source_red and _source_can_produce(by_key[m.source_red]))
    has_blue = bool(m.blue_ctrl) or blue_later
    has_red = bool(m.red_ctrl) or red_later
    if m.blue_ctrl and not has_red:
        m.winner_ctrl = m.blue_ctrl
        m.is_bye = True
    elif m.red_ctrl and not has_blue:
        m.winner_ctrl = m.red_ctrl
        m.is_bye = True


def build_bracket(n: int, *, bronze_bout: bool = False) -> Bracket:
    if n < 0:
        raise ValueError("n < 0")
    if n > 64:
        raise ValueError("В категории больше 64 участников: сетка не строится")
    if n == 0:
        return Bracket(0, 0, "empty")

    size = bracket_size(n)
    first = first_round_order(n)
    matches: list[MatchSpec] = []
    current: list[MatchSpec] = []
    for i, slot in enumerate(first):
        if slot.kind == "empty":
            m = MatchSpec(
                key=f"R1-{i}",
                round_code=_round_name(len(first), False),
                slot=i,
                is_bye=True,
            )
        elif slot.kind == "bye":
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
        code = "финал" if is_last else _round_name(len(current) // 2, False)
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

    bracket = Bracket(n, size, "single_elim", first, matches)
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
        if m.source_blue:
            src = by_key[m.source_blue]
            if m.round_code == "за бронзу":
                m.blue_ctrl = loser_of(src)
            else:
                m.blue_ctrl = src.winner_ctrl
        if m.source_red:
            src = by_key[m.source_red]
            if m.round_code == "за бронзу":
                m.red_ctrl = loser_of(src)
            else:
                m.red_ctrl = src.winner_ctrl
        if m.is_bye and m.winner_ctrl and m.winner_ctrl not in {m.blue_ctrl, m.red_ctrl}:
            m.winner_ctrl = m.blue_ctrl or m.red_ctrl
        if m.winner_ctrl is not None and m.winner_ctrl not in {m.blue_ctrl, m.red_ctrl}:
            m.winner_ctrl = None
        if not m.is_bye:
            _fill_bye(m, by_key)
        elif not m.blue_ctrl and not m.red_ctrl:
            m.winner_ctrl = None


def loser_of(match: MatchSpec) -> int | None:
    if match.winner_ctrl is None or match.blue_ctrl is None or match.red_ctrl is None:
        return None
    return match.red_ctrl if match.winner_ctrl == match.blue_ctrl else match.blue_ctrl


def propagate(bracket: Bracket) -> None:
    """Продвинуть уже записанных победителей по сетке."""
    _propagate(bracket)


def fight_count(n: int, bronze_bout: bool = False) -> int:
    if n <= 1:
        return 0
    extra = 1 if bronze_bout and n >= 4 else 0
    return n - 1 + extra
