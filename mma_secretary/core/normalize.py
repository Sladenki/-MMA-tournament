from __future__ import annotations

import re
from typing import Iterable


_SPACE = re.compile(r"\s+")


def normalize_name(raw: str | None) -> str:
    """Обрезать пробелы, каждое слово с заглавной, оставить фамилию и имя."""
    if not raw:
        return ""
    words = _SPACE.split(str(raw).strip())
    words = [w for w in words if w]
    if len(words) > 2:
        words = words[:2]
    return " ".join(w[:1].upper() + w[1:].lower() if w else w for w in words)


def normalize_rank(raw: str | None) -> str:
    if raw is None:
        return ""
    return _SPACE.sub(" ", str(raw).strip()).upper()


def normalize_org(raw: str | None) -> str:
    if raw is None:
        return ""
    return _SPACE.sub(" ", str(raw).strip())


def parse_weight(raw: str | int | float | None) -> float | None:
    if raw is None or raw == "":
        return None
    if isinstance(raw, (int, float)):
        return float(raw)
    text = str(raw).strip().replace(" ", "").replace(",", ".")
    if not text:
        return None
    return float(text)


def parse_age_bounds(label: str) -> tuple[int, int]:
    """Разобрать подпись группы. «N+» и «младше N» — год рождения >= N (как в старом файле)."""
    text = (label or "").strip()
    m = re.search(r"(\d{4})\s*[-–—]\s*(\d{4})", text)
    if m:
        a, b = int(m.group(1)), int(m.group(2))
        return (min(a, b), max(a, b))
    m = re.search(r"младше\s*(\d{4})", text, re.IGNORECASE)
    if m:
        return (int(m.group(1)), 3000)
    m = re.search(r"(\d{4})\s*\+", text)
    if m:
        return (int(m.group(1)), 3000)
    m = re.search(r"(\d{4})", text)
    if m:
        y = int(m.group(1))
        return (y, y)
    raise ValueError(f"Не удалось разобрать возрастную группу: {label!r}")


def format_kg(value: float) -> str:
    text = f"{value:.1f}".replace(".", ",")
    if text.endswith(",0"):
        return text[:-2]
    return text


def looks_like_duplicate(a_name: str, a_year: int | None, others: Iterable[tuple[str, int | None]]) -> bool:
    key = (normalize_name(a_name).casefold(), a_year)
    for name, year in others:
        if (normalize_name(name).casefold(), year) == key:
            return True
    return False
