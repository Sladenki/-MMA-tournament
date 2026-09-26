"""Сборка локальной базы и сервиса. Роутеры берут их отсюда, а не создают свои."""

from __future__ import annotations

from mma_secretary.paths import data_dir, photos_dir, static_dir
from mma_secretary.services.archives import Archives
from mma_secretary.services.engine import TournamentService
from mma_secretary.storage.db import Database

STATIC = static_dir()
PHOTOS = photos_dir()
DATA_DIR = data_dir()
DB_PATH = DATA_DIR / "tournament.db"

db = Database(DB_PATH)
svc = TournamentService(db)
svc.seed_defaults()
archives = Archives(DATA_DIR / "saves", svc)
