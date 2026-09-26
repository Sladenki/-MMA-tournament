from __future__ import annotations

from fastapi import APIRouter, HTTPException
from fastapi.responses import FileResponse, HTMLResponse

from mma_secretary.paths import manual_path
from mma_secretary.web.deps import STATIC

router = APIRouter()


@router.get("/favicon.ico", include_in_schema=False)
def favicon():
    return FileResponse(STATIC / "favicon.ico")


@router.get("/instruction.docx", include_in_schema=False)
def instruction():
    path = manual_path()
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Инструкция не найдена")
    return FileResponse(
        path,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="Инструкция для секретаря.docx",
    )


@router.get("/", response_class=HTMLResponse)
def index():
    return (STATIC / "index.html").read_text(encoding="utf-8")


@router.get("/about", response_class=HTMLResponse)
def about():
    return (STATIC / "about.html").read_text(encoding="utf-8")
