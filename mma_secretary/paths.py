"""Где лежат файлы программы и где лежит база турнира.

В обычном запуске это папка проекта.
В exe база и фото лежат рядом с файлом программы, а не во временной папке.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path


def frozen() -> bool:
    return bool(getattr(sys, "frozen", False))


def project_dir() -> Path:
    if frozen():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def data_dir() -> Path:
    raw = os.environ.get("MMA_DATA_DIR")
    path = Path(raw) if raw else project_dir() / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def photos_dir() -> Path:
    return project_dir() / "photos"


def static_dir() -> Path:
    return Path(__file__).resolve().parent / "web" / "static"


def gold_fixture() -> Path:
    bundled = Path(__file__).resolve().parent / "fixtures" / "gold_2024.json"
    if bundled.is_file():
        return bundled
    return project_dir() / "tests" / "fixtures" / "gold_2024.json"
