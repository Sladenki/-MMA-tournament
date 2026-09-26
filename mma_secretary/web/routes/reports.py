from __future__ import annotations

from fastapi import APIRouter

from mma_secretary.web.deps import svc

router = APIRouter()


@router.get("/api/placements")
def places():
    return svc.placements_report()


@router.get("/api/teams")
def teams():
    return svc.team_report()


@router.post("/api/teams/rep")
def rep(data: dict):
    svc.set_representative(data["organization"], data.get("representative") or "")
    return {"ok": True}


@router.get("/api/mandate")
def mandate():
    return svc.mandate()


@router.get("/api/medalists")
def medals():
    return svc.medalists()
