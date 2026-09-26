"""Личные места, командный зачёт и мандатная комиссия."""

from __future__ import annotations

from mma_secretary.core.normalize import normalize_rank
from mma_secretary.core.team import team_standings

_TITLES = ("ЗМС", "МСМК", "МС", "КМС")


class ReportsMixin:
    conn: object

    def placements_report(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT pl.*, p.name, p.organization, p.rank, p.birth_year, p.coach,
                      ag.label AS age_label, d.code AS division_code, w.label AS weight_label
               FROM placement pl
               JOIN participant p ON p.id=pl.participant_id
               JOIN category c ON c.id=pl.category_id
               JOIN age_group ag ON ag.id=c.age_group_id
               JOIN division d ON d.id=c.division_id
               JOIN weight_class w ON w.id=c.weight_class_id
               ORDER BY ag.sort_order, d.sort_order, w.limit_kg, pl.place""",
            (),
        ).fetchall()
        return [dict(r) for r in rows]

    def team_report(self) -> list[dict]:
        raw = []
        for r in self.placements_report():
            cat = f"{r['age_label']} / {r['division_code']} / {r['weight_label']}"
            raw.append((r["organization"], r["points"], cat, r["place"]))
        standings = team_standings(raw)
        return [
            {
                "organization": s.organization,
                "points": s.points,
                "place": s.place,
                "category_places": s.category_places,
                "representative": self._rep(s.organization),
            }
            for s in standings
        ]

    def _rep(self, org: str) -> str:
        r = self.conn.execute(
            "SELECT representative FROM team_rep WHERE tournament_id=? AND organization=?",
            (self.tid(), org),
        ).fetchone()
        return r["representative"] if r else ""

    def set_representative(self, organization: str, name: str) -> None:
        self.conn.execute(
            """INSERT INTO team_rep (tournament_id, organization, representative) VALUES (?,?,?)
               ON CONFLICT(tournament_id, organization) DO UPDATE SET representative=excluded.representative""",
            (self.tid(), organization, name),
        )
        self.conn.commit()

    def mandate(self) -> dict:
        weights = self.list_weights()
        orgs = sorted({p["organization"] or "—" for p in self.list_participants() if p["status"] not in {"снят"}})
        grid = {org: {w.label: 0 for w in weights} for org in orgs}
        titles = {t: 0 for t in _TITLES}
        titles["1–3 разряд"] = 0
        placed_ids = {r["participant_id"] for r in self.conn.execute(
            "SELECT participant_id FROM category_entry e JOIN category c ON c.id=e.category_id WHERE c.tournament_id=?",
            (self.tid(),),
        )}
        for p in self.list_participants():
            if p["id"] not in placed_ids:
                continue
            org = p["organization"] or "—"
            entry = self.conn.execute(
                """SELECT w.label FROM category_entry e
                   JOIN category c ON c.id=e.category_id
                   JOIN weight_class w ON w.id=c.weight_class_id
                   WHERE e.participant_id=?""",
                (p["id"],),
            ).fetchone()
            if entry and org in grid:
                grid[org][entry["label"]] = grid[org].get(entry["label"], 0) + 1
            rank = normalize_rank(p["rank"])
            if rank in titles:
                titles[rank] += 1
            elif rank in {"1", "2", "3", "1 РАЗРЯД", "2 РАЗРЯД", "3 РАЗРЯД"}:
                titles["1–3 разряд"] += 1
        rows = []
        for org in orgs:
            cells = grid.get(org, {})
            rows.append(
                {
                    "organization": org,
                    "cells": cells,
                    "total": sum(cells.values()),
                    "representative": self._rep(org),
                }
            )
        col_totals = {w.label: sum(r["cells"].get(w.label, 0) for r in rows) for w in weights}
        return {
            "weights": [w.label for w in weights],
            "rows": rows,
            "col_totals": col_totals,
            "grand_total": sum(r["total"] for r in rows),
            "titles": titles,
        }

    def medalists(self) -> list[dict]:
        return [r for r in self.placements_report() if r["place"] <= 3]
