"""Сборка локальной базы и сервиса. Роутеры берут их отсюда, а не создают свои."""

from __future__ import annotations

import os
from pathlib import Path

from mma_secretary.services.archives import Archives
from mma_secretary.services.engine import TournamentService
from mma_secretary.storage.db import Database

STATIC = Path(__file__).parent / "static"
PHOTOS = Path(__file__).resolve().parents[2] / "photos"
DATA_DIR = Path(os.environ.get("MMA_DATA_DIR", Path(__file__).resolve().parents[2] / "data"))
DATA_DIR.mkdir(exist_ok=True)
DB_PATH = DATA_DIR / "tournament.db"

db = Database(DB_PATH)
svc = TournamentService(db)
svc.seed_defaults()
archives = Archives(DATA_DIR / "saves", svc)
