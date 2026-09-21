from __future__ import annotations

from collections import defaultdict

from mma_secretary.core.models import TeamRow


def team_standings(
    rows: list[tuple[str, int, str, int]],
) -> list[TeamRow]:
    """rows: (organization, points, category_label, place)."""
    totals: dict[str, int] = defaultdict(int)
    by_cat: dict[str, dict[str, list[int]]] = defaultdict(lambda: defaultdict(list))
    for org, pts, cat, place in rows:
        org = org or "—"
        totals[org] += pts
        by_cat[org][cat].append(place)

    ranked = sorted(totals.items(), key=lambda x: (-x[1], x[0].casefold()))
    result: list[TeamRow] = []
    for org, pts in ranked:
        better = sum(1 for _, other in ranked if other > pts)
        result.append(
            TeamRow(
                organization=org,
                points=pts,
                place=1 + better,
                category_places={k: sorted(v) for k, v in by_cat[org].items()},
            )
        )
    return result
