from __future__ import annotations

import secrets
from collections.abc import Sequence

from mma_secretary.core.models import Participant


def assign_control_numbers(participants: Sequence[Participant]) -> list[tuple[int, int]]:
    """Сортировка по номеру жребия по возрастанию, затем контрольные 1…n.

    Возвращает список (participant_id, control_number).
    """
    def sort_key(p: Participant) -> tuple:
        draw = p.draw_number
        return (draw is None, draw if draw is not None else 10**9, p.name.casefold(), p.id)

    ordered = sorted(participants, key=sort_key)
    return [(p.id, i) for i, p in enumerate(ordered, start=1)]


def redraw_control_numbers(
    control_ids: Sequence[int],
    *,
    seed: int | None = None,
) -> tuple[list[tuple[int, int]], int]:
    """Случайная перестановка контрольных номеров 1…n.

    Возвращает ([(participant_id, new_ctrl)], seed).
    """
    ids = list(control_ids)
    n = len(ids)
    if seed is None:
        seed = secrets.randbits(32)
    rng = _rng(seed)
    numbers = list(range(1, n + 1))
    _shuffle(numbers, rng)
    return list(zip(ids, numbers)), seed


def _rng(seed: int):
    import random

    return random.Random(seed)


def _shuffle(items: list, rng) -> None:
    for i in range(len(items) - 1, 0, -1):
        j = rng.randrange(i + 1)
        items[i], items[j] = items[j], items[i]
