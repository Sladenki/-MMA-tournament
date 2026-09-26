"""Реквизиты турнира и справочники: возраст, дивизион, вес, очки."""

from __future__ import annotations

import json

from mma_secretary.core.models import DEFAULT_POINT_RULES, AgeGroup, Division, PointRule, WeightClass
from mma_secretary.core.normalize import format_kg, normalize_rank, parse_age_bounds, parse_weight
from mma_secretary.services.common import _row


class CatalogMixin:
    conn: object

    def ensure_tournament(self) -> int:
        row = self.conn.execute("SELECT id FROM tournament LIMIT 1").fetchone()
        if row:
            tid = row["id"]
        else:
            cur = self.conn.execute(
                "INSERT INTO tournament (name, kind) VALUES (?, ?)",
                ("", "смешанное боевое единоборство (ММА)"),
            )
            tid = cur.lastrowid
            for rule in DEFAULT_POINT_RULES:
                self.conn.execute(
                    "INSERT INTO point_rule (tournament_id, place_from, place_to, points) VALUES (?,?,?,?)",
                    (tid, rule.place_from, rule.place_to, rule.points),
                )
            self.conn.commit()
        return tid

    def tid(self) -> int:
        return self.ensure_tournament()

    def get_tournament(self) -> dict:
        return _row(self.conn.execute("SELECT * FROM tournament WHERE id=?", (self.tid(),)).fetchone())

    def update_tournament(self, data: dict) -> dict:
        fields = (
            "name",
            "kind",
            "date",
            "city",
            "chief_referee",
            "chief_secretary",
            "rings",
            "bronze_bout",
            "two_bronzes",
            "award_walkover",
        )
        sets, vals = [], []
        for f in fields:
            if f in data:
                sets.append(f"{f}=?")
                vals.append(data[f])
        if sets:
            vals.append(self.tid())
            self.conn.execute(f"UPDATE tournament SET {', '.join(sets)} WHERE id=?", vals)
            self.conn.commit()
        return self.get_tournament()

    def list_age_groups(self) -> list[AgeGroup]:
        rows = self.conn.execute(
            "SELECT * FROM age_group WHERE tournament_id=? ORDER BY sort_order, year_from, id",
            (self.tid(),),
        ).fetchall()
        return [AgeGroup(r["id"], r["label"], r["year_from"], r["year_to"], r["sort_order"]) for r in rows]

    def save_age_group(self, data: dict) -> dict:
        label = (data.get("label") or "").strip()
        if "year_from" in data and "year_to" in data:
            yf, yt = int(data["year_from"]), int(data["year_to"])
        else:
            yf, yt = parse_age_bounds(label)
        order = int(data.get("sort_order") or 0)
        if data.get("id"):
            self.conn.execute(
                "UPDATE age_group SET label=?, year_from=?, year_to=?, sort_order=? WHERE id=?",
                (label, yf, yt, order, data["id"]),
            )
            gid = data["id"]
        else:
            cur = self.conn.execute(
                "INSERT INTO age_group (tournament_id, label, year_from, year_to, sort_order) VALUES (?,?,?,?,?)",
                (self.tid(), label, yf, yt, order),
            )
            gid = cur.lastrowid
        self.conn.commit()
        return _row(self.conn.execute("SELECT * FROM age_group WHERE id=?", (gid,)).fetchone())

    def delete_age_group(self, gid: int) -> None:
        self.conn.execute("DELETE FROM age_group WHERE id=?", (gid,))
        self.conn.commit()

    def list_divisions(self) -> list[Division]:
        rows = self.conn.execute(
            "SELECT * FROM division WHERE tournament_id=? ORDER BY sort_order, id",
            (self.tid(),),
        ).fetchall()
        out = []
        for r in rows:
            vals = tuple(json.loads(r["rank_values"] or "[]"))
            out.append(Division(r["id"], r["code"], r["sort_order"], vals))
        return out

    def save_division(self, data: dict) -> dict:
        code = normalize_rank(data.get("code"))
        order = int(data.get("sort_order") or 0)
        ranks = data.get("rank_values") or []
        if isinstance(ranks, str):
            ranks = [x.strip() for x in ranks.split(",") if x.strip()]
        payload = json.dumps([normalize_rank(x) for x in ranks], ensure_ascii=False)
        if data.get("id"):
            self.conn.execute(
                "UPDATE division SET code=?, sort_order=?, rank_values=? WHERE id=?",
                (code, order, payload, data["id"]),
            )
            did = data["id"]
        else:
            cur = self.conn.execute(
                "INSERT INTO division (tournament_id, code, sort_order, rank_values) VALUES (?,?,?,?)",
                (self.tid(), code, order, payload),
            )
            did = cur.lastrowid
        self.conn.commit()
        return _row(self.conn.execute("SELECT * FROM division WHERE id=?", (did,)).fetchone())

    def delete_division(self, did: int) -> None:
        self.conn.execute("DELETE FROM division WHERE id=?", (did,))
        self.conn.commit()

    def list_weights(self) -> list[WeightClass]:
        rows = self.conn.execute(
            "SELECT * FROM weight_class WHERE tournament_id=? ORDER BY sort_order, limit_kg, id",
            (self.tid(),),
        ).fetchall()
        return [
            WeightClass(r["id"], r["limit_kg"], r["label"], r["age_group_id"], r["sort_order"])
            for r in rows
        ]

    def save_weight(self, data: dict) -> dict:
        limit = parse_weight(data.get("limit_kg"))
        if limit is None:
            raise ValueError("Нужна верхняя граница веса")
        label = (data.get("label") or format_kg(limit)).strip()
        order = int(data.get("sort_order") or 0)
        age_id = data.get("age_group_id")
        if data.get("id"):
            self.conn.execute(
                "UPDATE weight_class SET limit_kg=?, label=?, sort_order=?, age_group_id=? WHERE id=?",
                (limit, label, order, age_id, data["id"]),
            )
            wid = data["id"]
        else:
            cur = self.conn.execute(
                "INSERT INTO weight_class (tournament_id, age_group_id, limit_kg, label, sort_order) VALUES (?,?,?,?,?)",
                (self.tid(), age_id, limit, label, order),
            )
            wid = cur.lastrowid
        self._sort_weights()
        return _row(self.conn.execute("SELECT * FROM weight_class WHERE id=?", (wid,)).fetchone())

    def _sort_weights(self) -> None:
        rows = self.conn.execute(
            "SELECT id FROM weight_class WHERE tournament_id=? ORDER BY limit_kg, id",
            (self.tid(),),
        ).fetchall()
        for i, r in enumerate(rows):
            self.conn.execute("UPDATE weight_class SET sort_order=? WHERE id=?", (i, r["id"]))
        self.conn.commit()

    def delete_weight(self, wid: int) -> None:
        self.conn.execute("DELETE FROM weight_class WHERE id=?", (wid,))
        self.conn.commit()

    def list_point_rules(self) -> list[PointRule]:
        rows = self.conn.execute(
            "SELECT * FROM point_rule WHERE tournament_id=? ORDER BY place_from",
            (self.tid(),),
        ).fetchall()
        return [PointRule(r["place_from"], r["place_to"], r["points"]) for r in rows]

    def replace_point_rules(self, rules: list[dict]) -> list[dict]:
        tid = self.tid()
        self.conn.execute("DELETE FROM point_rule WHERE tournament_id=?", (tid,))
        for r in rules:
            self.conn.execute(
                "INSERT INTO point_rule (tournament_id, place_from, place_to, points) VALUES (?,?,?,?)",
                (tid, int(r["place_from"]), int(r["place_to"]), int(r["points"])),
            )
        self.conn.commit()
        return [dict(x) for x in self.conn.execute("SELECT * FROM point_rule WHERE tournament_id=? ORDER BY place_from", (tid,))]
