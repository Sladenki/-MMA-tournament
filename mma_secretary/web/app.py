from __future__ import annotations

import json
import os
from pathlib import Path

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

from mma_secretary.services.documents import (
    brackets_html,
    certificates,
    corner_list,
    full_report,
    medalists_html,
    pair_list,
    personal_results,
    protocol_mandate,
    protocol_weigh_in,
    scorecards,
    team_protocol,
)
from mma_secretary.services.archives import Archives
from mma_secretary.services.engine import TournamentService
from mma_secretary.services.import_export import export_participants_xlsx, export_report_xlsx, import_xlsx
from mma_secretary.storage.db import Database

STATIC = Path(__file__).parent / "static"
DATA_DIR = Path(os.environ.get("MMA_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "tournament.db"

db = Database(DB_PATH)
svc = TournamentService(db)
svc.seed_defaults()
archives = Archives(DATA_DIR / "saves", svc)

app = FastAPI(title="Секретарь ММА", version="1.0.0")
app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@app.get("/about", response_class=HTMLResponse)
def about():
    return (STATIC / "about.html").read_text(encoding="utf-8")


def _err(exc: Exception):
    raise HTTPException(400, str(exc)) from exc


@app.get("/api/bootstrap")
def bootstrap():
    return {
        "tournament": svc.get_tournament(),
        "age_groups": [a.__dict__ for a in svc.list_age_groups()],
        "divisions": [{"id": d.id, "code": d.code, "sort_order": d.sort_order, "rank_values": list(d.rank_values)} for d in svc.list_divisions()],
        "weights": [w.__dict__ for w in svc.list_weights()],
        "point_rules": [p.__dict__ for p in svc.list_point_rules()],
    }


@app.put("/api/tournament")
def put_tournament(data: dict):
    return svc.update_tournament(data)


@app.post("/api/age-groups")
def post_age(data: dict):
    try:
        return svc.save_age_group(data)
    except Exception as e:
        _err(e)


@app.delete("/api/age-groups/{gid}")
def del_age(gid: int):
    svc.delete_age_group(gid)
    return {"ok": True}


@app.post("/api/divisions")
def post_div(data: dict):
    return svc.save_division(data)


@app.delete("/api/divisions/{did}")
def del_div(did: int):
    svc.delete_division(did)
    return {"ok": True}


@app.post("/api/weights")
def post_w(data: dict):
    try:
        return svc.save_weight(data)
    except Exception as e:
        _err(e)


@app.delete("/api/weights/{wid}")
def del_w(wid: int):
    svc.delete_weight(wid)
    return {"ok": True}


@app.put("/api/points")
def put_points(rules: list[dict]):
    return svc.replace_point_rules(rules)


@app.get("/api/participants")
def get_parts(sort: str = "seq"):
    return svc.list_participants(sort)


@app.post("/api/participants")
def post_part(data: dict):
    try:
        return svc.add_participant(data)
    except Exception as e:
        _err(e)


@app.put("/api/participants/{pid}")
def put_part(pid: int, data: dict):
    try:
        return svc.update_participant(pid, data)
    except Exception as e:
        _err(e)


@app.delete("/api/participants/{pid}")
def del_part(pid: int):
    svc.delete_participant(pid)
    return {"ok": True}


@app.post("/api/participants/{pid}/weigh")
def weigh(pid: int, data: dict):
    try:
        return svc.weigh_in(pid, data.get("weight"), data.get("status"))
    except Exception as e:
        _err(e)


@app.get("/api/participants/{pid}/weights")
def hist(pid: int):
    return svc.weight_history(pid)


@app.post("/api/participants/import")
async def import_parts(file: UploadFile = File(...)):
    raw = await file.read()
    try:
        return import_xlsx(svc, raw)
    except Exception as e:
        _err(e)


@app.post("/api/classify")
def classify():
    return svc.classify()


@app.get("/api/categories")
def cats():
    return svc.list_categories()


@app.get("/api/categories/{cid}")
def cat(cid: int):
    return svc.category_detail(cid)


@app.post("/api/categories/{cid}/redraw")
def redraw(cid: int, data: dict | None = None):
    seed = (data or {}).get("seed")
    return svc.redraw(cid, seed=seed)


@app.post("/api/categories/{cid}/order")
def order(cid: int, data: dict):
    try:
        return svc.manual_order(cid, data["participant_ids"])
    except Exception as e:
        _err(e)


@app.get("/api/bouts")
def bouts():
    return svc.list_bouts()


@app.post("/api/bouts/{bid}/result")
def result(bid: int, data: dict):
    try:
        return svc.set_result(bid, int(data["winner_entry_id"]), data.get("method"))
    except Exception as e:
        _err(e)


@app.post("/api/bouts/{bid}/clear")
def clear(bid: int):
    try:
        return svc.clear_bout(bid)
    except Exception as e:
        _err(e)


@app.post("/api/bouts/{bid}/schedule")
def sched(bid: int, data: dict):
    return svc.schedule_bout(bid, data.get("ring"), data.get("scheduled_order"))


@app.get("/api/placements")
def places():
    return svc.placements_report()


@app.get("/api/teams")
def teams():
    return svc.team_report()


@app.post("/api/teams/rep")
def rep(data: dict):
    svc.set_representative(data["organization"], data.get("representative") or "")
    return {"ok": True}


@app.get("/api/mandate")
def mandate():
    return svc.mandate()


@app.get("/api/medalists")
def medals():
    return svc.medalists()


@app.post("/api/undo")
def undo():
    try:
        return svc.undo()
    except Exception as e:
        _err(e)


@app.get("/api/export")
def export_json():
    payload = json.dumps(svc.export_bundle(), ensure_ascii=False, indent=2, default=str)
    return Response(payload, media_type="application/json", headers={"Content-Disposition": "attachment; filename=tournament.json"})


@app.post("/api/import")
async def import_json(file: UploadFile = File(...)):
    data = json.loads(await file.read())
    svc.import_bundle(data)
    return {"ok": True}


@app.get("/api/saves")
def list_saves():
    return archives.list()


@app.post("/api/saves")
def create_save(data: dict):
    return archives.save(data.get("name") or "")


@app.post("/api/saves/{sid}/load")
def load_save(sid: str):
    try:
        archives.load(sid)
        return {"ok": True}
    except Exception as e:
        _err(e)


@app.delete("/api/saves/{sid}")
def delete_save(sid: str):
    archives.delete(sid)
    return {"ok": True}


@app.post("/api/tournament/new")
def new_tournament():
    svc.reset_to_empty()
    return {"ok": True}


@app.get("/api/export/participants.xlsx")
def x_parts():
    return Response(
        export_participants_xlsx(svc),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=participants.xlsx"},
    )


@app.get("/api/export/report.xlsx")
def x_rep():
    return Response(
        export_report_xlsx(svc),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": "attachment; filename=report.xlsx"},
    )


def _html(name: str, fn):
    return HTMLResponse(
        fn(svc),
        headers={"Cache-Control": "no-store", "Content-Type": "text/html; charset=utf-8"},
    )


@app.get("/print/weigh-in")
def p1():
    return _html("weigh-in", protocol_weigh_in)


@app.get("/print/mandate")
def p2():
    return _html("mandate", protocol_mandate)


@app.get("/print/pairs")
def p3():
    return _html("pairs", pair_list)


@app.get("/print/corners")
def p4():
    return _html("corners", corner_list)


@app.get("/print/brackets")
def p5():
    return _html("brackets", brackets_html)


@app.get("/print/personal")
def p6():
    return _html("personal", personal_results)


@app.get("/print/scorecards")
def p7():
    return _html("scorecards", scorecards)


@app.get("/print/teams")
def p8():
    return _html("teams", team_protocol)


@app.get("/print/medals")
def p9():
    return _html("medals", medalists_html)


@app.get("/print/certificates")
def p10():
    return _html("certificates", certificates)


@app.get("/print/report")
def p11():
    return _html("report", full_report)


@app.post("/api/demo")
def demo():
    """Загрузить 14 участников из эталонного файла 14.09.2024."""
    gold = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "gold_2024.json"
    data = json.loads(gold.read_text(encoding="utf-8"))
    svc.seed_defaults()
    existing = {p["name"] for p in svc.list_participants()}
    for p in data["participants"]:
        if p["name"] in existing:
            continue
        svc.add_participant(
            {
                "seq": p["n"],
                "draw_number": p["draw"],
                "name": p["name"],
                "organization": p["org"],
                "rank": p["rank"],
                "birth_year": p["year"],
                "coach": p["coach"],
                "weight": p["weight"],
            }
        )
    return {"ok": True, "n": len(svc.list_participants())}
