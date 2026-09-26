from __future__ import annotations

from fastapi import APIRouter
from fastapi.responses import HTMLResponse

from mma_secretary.web.deps import STATIC

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@router.get("/about", response_class=HTMLResponse)
def about():
    return (STATIC / "about.html").read_text(encoding="utf-8")
