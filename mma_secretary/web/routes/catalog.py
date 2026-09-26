from __future__ import annotations

from fastapi import APIRouter

from mma_secretary.paths import frozen
from mma_secretary.web.deps import svc
from mma_secretary.web.errors import bad_request

router = APIRouter()


@router.get("/api/bootstrap")
def bootstrap():
    return {
        "tournament": svc.get_tournament(),
        "age_groups": [a.__dict__ for a in svc.list_age_groups()],
        "divisions": [
            {"id": d.id, "code": d.code, "sort_order": d.sort_order, "rank_values": list(d.rank_values)}
            for d in svc.list_divisions()
        ],
        "weights": [w.__dict__ for w in svc.list_weights()],
        "point_rules": [p.__dict__ for p in svc.list_point_rules()],
        "keeps_documents": frozen(),
    }


@router.put("/api/tournament")
def put_tournament(data: dict):
    return svc.update_tournament(data)


@router.post("/api/age-groups")
def post_age(data: dict):
    try:
        return svc.save_age_group(data)
    except Exception as e:
        bad_request(e)


@router.delete("/api/age-groups/{gid}")
def del_age(gid: int):
    svc.delete_age_group(gid)
    return {"ok": True}


@router.post("/api/divisions")
def post_div(data: dict):
    return svc.save_division(data)


@router.delete("/api/divisions/{did}")
def del_div(did: int):
    svc.delete_division(did)
    return {"ok": True}


@router.post("/api/weights")
def post_w(data: dict):
    try:
        return svc.save_weight(data)
    except Exception as e:
        bad_request(e)


@router.delete("/api/weights/{wid}")
def del_w(wid: int):
    svc.delete_weight(wid)
    return {"ok": True}


@router.put("/api/points")
def put_points(rules: list[dict]):
    return svc.replace_point_rules(rules)
