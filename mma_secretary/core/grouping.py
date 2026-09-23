from __future__ import annotations

from mma_secretary.core.models import (
    AgeGroup,
    CategoryKey,
    Division,
    Participant,
    Unplaced,
    WeightClass,
)
from mma_secretary.core.normalize import normalize_gender, normalize_rank


def age_group_for(birth_year: int | None, groups: list[AgeGroup]) -> AgeGroup | None:
    if birth_year is None:
        return None
    ordered = sorted(groups, key=lambda g: (g.sort_order, g.year_from, g.id))
    for g in ordered:
        lo, hi = g.year_from, g.year_to
        if lo > hi:
            lo, hi = hi, lo
        if lo <= birth_year <= hi:
            return g
    return None


def division_for(participant: Participant, divisions: list[Division]) -> Division | None:
    """Разряд остаётся на человеке. Дивизион берём отдельно, иначе первый в справочнике."""
    if not divisions:
        return None
    ordered = sorted(divisions, key=lambda d: (d.sort_order, d.id))
    if participant.division_id:
        for d in ordered:
            if d.id == participant.division_id:
                return d
    codes = {d.code.strip().upper(): d for d in ordered}
    r = normalize_rank(participant.rank)
    if r in codes:
        return codes[r]
    return ordered[0]


def weight_class_for(weight: float | None, classes: list[WeightClass]) -> WeightClass | None:
    if weight is None:
        return None
    ordered = sorted(classes, key=lambda w: (w.sort_order, w.limit_kg, w.id))
    if not ordered:
        return None
    for wc in ordered:
        if weight <= wc.limit_kg + 1e-9:
            return wc
    return None


def classify_participant(
    participant: Participant,
    groups: list[AgeGroup],
    divisions: list[Division],
    weights: list[WeightClass],
    *,
    require_weighed: bool = True,
) -> tuple[CategoryKey | None, Unplaced | None]:
    if participant.status in {"снят", "не явился"}:
        return None, Unplaced(participant.id, f"статус «{participant.status}»")
    if require_weighed and participant.weight is None:
        return None, Unplaced(participant.id, "нет фактического веса")
    age = age_group_for(participant.birth_year, groups)
    if age is None:
        return None, Unplaced(participant.id, "год рождения не попал ни в одну возрастную группу")
    div = division_for(participant, divisions)
    if div is None:
        return None, Unplaced(participant.id, "в справочнике нет дивизиона")
    scoped = [w for w in weights if w.age_group_id in (None, age.id)]
    wc = weight_class_for(participant.weight, scoped)
    if wc is None:
        if participant.weight is None:
            return None, Unplaced(participant.id, "нет фактического веса")
        return None, Unplaced(participant.id, f"вес {participant.weight} кг выше самой тяжёлой категории — снят")
    gender = normalize_gender(participant.gender)
    return CategoryKey(age.id, div.id, wc.id, gender), None


def classify_all(
    participants: list[Participant],
    groups: list[AgeGroup],
    divisions: list[Division],
    weights: list[WeightClass],
) -> tuple[dict[CategoryKey, list[Participant]], list[Unplaced]]:
    buckets: dict[CategoryKey, list[Participant]] = {}
    unplaced: list[Unplaced] = []
    for p in participants:
        key, miss = classify_participant(p, groups, divisions, weights)
        if miss:
            unplaced.append(miss)
            continue
        assert key is not None
        buckets.setdefault(key, []).append(p)
    return buckets, unplaced
