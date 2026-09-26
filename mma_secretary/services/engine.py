"""Фасад турнира.

Правила живут в core и не знают про базу.
Новый кусок продукта — отдельный модуль здесь и свой роутер в web/routes.
"""

from __future__ import annotations

from mma_secretary.services.brackets import BracketsMixin
from mma_secretary.services.catalog import CatalogMixin
from mma_secretary.services.history import HistoryMixin
from mma_secretary.services.participants import ParticipantsMixin
from mma_secretary.services.reports import ReportsMixin
from mma_secretary.storage.db import Database


class TournamentService(CatalogMixin, ParticipantsMixin, BracketsMixin, ReportsMixin, HistoryMixin):
    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn
        self.ensure_tournament()
