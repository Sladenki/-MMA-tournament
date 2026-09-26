from __future__ import annotations

from fastapi import HTTPException


def bad_request(exc: Exception):
    raise HTTPException(400, str(exc)) from exc
