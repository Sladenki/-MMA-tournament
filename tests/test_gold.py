import json
from pathlib import Path

from mma_secretary.core.draw import assign_control_numbers
from mma_secretary.core.grouping import classify_all
from mma_secretary.core.models import AgeGroup, Division, Participant, WeightClass
from mma_secretary.core.normalize import format_kg

GOLD = json.loads((Path(__file__).parent / "fixtures" / "gold_2024.json").read_text(encoding="utf-8"))


def _setup():
    groups = [AgeGroup(1, "2007-2008", 2007, 2008)]
    divs = [Division(i + 1, c, i) for i, c in enumerate("АБВГД")]
    wts = [WeightClass(i + 1, kg, format_kg(kg)) for i, kg in enumerate(GOLD["weight_limits"])]
    parts = [
        Participant(
            id=p["n"],
            name=p["name"],
            organization=p["org"],
            rank=p["rank"] or "",
            birth_year=p["year"],
            coach=p["coach"],
            weight=p["weight"],
            status="взвешен",
            draw_number=p["draw"],
        )
        for p in GOLD["participants"]
    ]
    return groups, divs, wts, parts


def test_gold_all_fourteen_placed():
    groups, divs, wts, parts = _setup()
    buckets, unplaced = classify_all(parts, groups, divs, wts)
    assert unplaced == []
    assert sum(len(v) for v in buckets.values()) == 14


def test_gold_weight_split_and_control_order():
    groups, divs, wts, parts = _setup()
    buckets, _ = classify_all(parts, groups, divs, wts)
    by_label = {}
    for key, plist in buckets.items():
        wc = next(w for w in wts if w.id == key.weight_class_id)
        names = [p.name for p, _ctrl in zip(
            sorted(plist, key=lambda x: (x.draw_number, x.id)),
            range(len(plist)),
        )]
        assigned = assign_control_numbers(plist)
        id_to_name = {p.id: p.name for p in plist}
        ordered = [id_to_name[pid] for pid, _ in sorted(assigned, key=lambda x: x[1])]
        by_label[wc.label] = ordered
        assert [c for _, c in sorted(assigned, key=lambda x: x[1])] == list(range(1, len(plist) + 1))
    for label, expected in GOLD["expected_categories"].items():
        got = by_label.get(label, [])
        assert got == expected, (label, got, expected)
