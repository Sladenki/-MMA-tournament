from __future__ import annotations

from collections import defaultdict

from mma_secretary.core.models import TeamRow


def team_standings(
    rows: list[tuple[str, int, str, int]],
) -> list[TeamRow]:
    """rows: (organization, points, category_label, place).

    При равенстве очков выше тот, у кого больше первых мест.
    """
    totals: dict[str, int] = defaultdict(int)
    golds: dict[str, int] = defaultdict(int)
    by_cat: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for org, pts, cat, place in rows:
        org = org or "—"
        totals[org] += pts
        if place == 1:
            golds[org] += 1
        by_cat[org][cat].append(place)

    ranked = sorted(totals.items(), key=lambda x: (-x[1], -golds[x[0]], x[0].casefold()))
    result: list[TeamRow] = []
    for org, pts in ranked:
        better = sum(
            1
            for other, other_pts in ranked
            if other_pts > pts or (other_pts == pts and golds[other] > golds[org])
        )
        result.append(
            TeamRow(
                organization=org,
                points=pts,
                place=1 + better,
                category_places={k: sorted(v) for k, v in by_cat[org].items()},
            )
        )
    return result
