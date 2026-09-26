"""Мелкие помощники сервисов. Без правил турнира и без HTTP."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r) -> dict[str, Any]:
    return dict(r) if r is not None else {}
