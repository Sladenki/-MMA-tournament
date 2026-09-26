from __future__ import annotations

from fastapi import APIRouter

from mma_secretary.web.deps import svc
from mma_secretary.web.errors import bad_request

router = APIRouter()


@router.post("/api/classify")
def classify():
    return svc.classify()


@router.get("/api/categories")
def cats():
    return svc.list_categories()


@router.get("/api/categories/{cid}")
def cat(cid: int):
    return svc.category_detail(cid)


@router.post("/api/categories/{cid}/redraw")
def redraw(cid: int, data: dict | None = None):
    seed = (data or {}).get("seed")
    return svc.redraw(cid, seed=seed)


@router.post("/api/categories/{cid}/order")
def order(cid: int, data: dict):
    try:
        return svc.manual_order(cid, data["participant_ids"])
    except Exception as e:
        bad_request(e)


@router.get("/api/bouts")
def bouts():
    return svc.list_bouts()


@router.post("/api/bouts/{bid}/result")
def result(bid: int, data: dict):
    try:
        return svc.set_result(bid, int(data["winner_entry_id"]))
    except Exception as e:
        bad_request(e)


@router.post("/api/bouts/{bid}/clear")
def clear(bid: int):
    try:
        return svc.clear_bout(bid)
    except Exception as e:
        bad_request(e)


@router.post("/api/bouts/{bid}/schedule")
def sched(bid: int, data: dict):
    return svc.schedule_bout(bid, data.get("ring"), data.get("scheduled_order"))
