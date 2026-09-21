import json
from pathlib import Path

from mma_secretary.core.normalize import format_kg
from mma_secretary.services.engine import TournamentService
from mma_secretary.storage.db import Database

GOLD = json.loads((Path(__file__).parent / "fixtures" / "gold_2024.json").read_text(encoding="utf-8"))


def test_classify_gold_roundtrip(tmp_path):
    db = Database(tmp_path / "t.db")
    svc = TournamentService(db)
    svc.update_tournament(GOLD["tournament"])
    svc.save_age_group({"label": "2007-2008", "year_from": 2007, "year_to": 2008})
    for i, code in enumerate("АБВГД"):
        svc.save_division({"code": code, "sort_order": i})
    for kg in GOLD["weight_limits"]:
        svc.save_weight({"limit_kg": kg, "label": format_kg(kg)})
    for p in GOLD["participants"]:
        svc.add_participant(
            {
                "seq": p["n"],
                "draw_number": p["draw"],
                "name": p["name"],
                "organization": p["org"],
                "birth_year": p["year"],
                "coach": p["coach"],
                "weight": p["weight"],
            }
        )
    result = svc.classify()
    assert result["unplaced"] == []
    by = {c["weight_label"]: c for c in result["categories"]}
    assert by["65,8"]["n"] == 3
    assert by["70,3"]["n"] == 4
    assert by["61,2"]["n"] == 2
    detail = svc.category_detail(by["65,8"]["id"])
    names = [e["name"] for e in detail["entries"]]
    assert names == GOLD["expected_categories"]["65,8"]
    four = svc.category_detail(by["70,3"]["id"])
    semis = [b for b in four["bouts"] if b["round_code"] == "1/2"]
    assert len(semis) == 2
    assert all(b["blue"] and b["red"] for b in semis)
    rr = [b for b in detail["bouts"] if not b["is_bye"]]
    assert len(rr) == 3
    first = rr[0]
    svc.set_result(first["id"], first["blue_entry_id"], "решение")
    again = svc.category_detail(by["65,8"]["id"])
    assert again["bouts"][0]["winner_entry_id"] == first["blue_entry_id"]
    svc.undo()
    undone = svc.category_detail(by["65,8"]["id"])
    assert undone["bouts"][0]["winner_entry_id"] is None
    db.close()
