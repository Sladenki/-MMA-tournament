from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from mma_secretary.core.bracket import apply_winner, build_bracket, clear_result
from mma_secretary.core.draw import assign_control_numbers, redraw_control_numbers
from mma_secretary.core.grouping import classify_all
from mma_secretary.core.models import (
    DEFAULT_POINT_RULES,
    AgeGroup,
    Bracket,
    Division,
    Participant,
    PointRule,
    WeightClass,
)
from mma_secretary.core.labels import bracket_kind_ru, round_ru
from mma_secretary.core.normalize import (
    format_kg,
    looks_like_duplicate,
    normalize_name,
    normalize_org,
    normalize_rank,
    parse_age_bounds,
    parse_weight,
)
from mma_secretary.core.placements import apply_points, placements_from_bracket
from mma_secretary.core.team import team_standings
from mma_secretary.storage.db import Database

TITLES = ("ЗМС", "МСМК", "МС", "КМС")


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _row(r) -> dict[str, Any]:
    return dict(r) if r is not None else {}


class TournamentService:
    def __init__(self, db: Database):
        self.db = db
        self.conn = db.conn
        self.ensure_tournament()

    # --- tournament & catalogs ---

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
            for i, rule in enumerate(DEFAULT_POINT_RULES):
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

    # --- participants ---

    def list_participants(self, sort: str = "seq") -> list[dict]:
        order = {
            "seq": "seq, id",
            "team": "organization COLLATE NOCASE, birth_year, draw_number, name",
            "weight": "weight IS NULL, weight, name",
            "year_weight": "birth_year, weight IS NULL, weight, name",
            "alpha": "name COLLATE NOCASE",
            "draw": "draw_number IS NULL, draw_number, name",
        }.get(sort, "seq, id")
        rows = self.conn.execute(
            f"SELECT * FROM participant WHERE tournament_id=? ORDER BY {order}",
            (self.tid(),),
        ).fetchall()
        return [dict(r) for r in rows]

    def _dup_warning(self, name: str, year: int | None, exclude_id: int | None = None) -> bool:
        others = []
        for r in self.list_participants():
            if exclude_id and r["id"] == exclude_id:
                continue
            others.append((r["name"], r["birth_year"]))
        return looks_like_duplicate(name, year, others)

    def add_participant(self, data: dict) -> dict:
        name = normalize_name(data.get("name"))
        if not name:
            raise ValueError("Нужны фамилия и имя")
        org = normalize_org(data.get("organization"))
        rank = normalize_rank(data.get("rank"))
        year = data.get("birth_year")
        year = int(year) if year not in (None, "") else None
        coach = (data.get("coach") or "").strip()
        weight = parse_weight(data.get("weight"))
        status = data.get("status") or ("взвешен" if weight is not None else "заявлен")
        draw = data.get("draw_number")
        draw = int(draw) if draw not in (None, "") else None
        seq = data.get("seq")
        if seq in (None, ""):
            mx = self.conn.execute(
                "SELECT COALESCE(MAX(seq),0) FROM participant WHERE tournament_id=?",
                (self.tid(),),
            ).fetchone()[0]
            seq = mx + 1
        warning = self._dup_warning(name, year)
        cur = self.conn.execute(
            """INSERT INTO participant
               (tournament_id, seq, name, organization, rank, birth_year, coach, weight, status, draw_number)
               VALUES (?,?,?,?,?,?,?,?,?,?)""",
            (self.tid(), seq, name, org, rank, year, coach, weight, status, draw),
        )
        pid = cur.lastrowid
        if weight is not None:
            self.conn.execute(
                "INSERT INTO weight_history (participant_id, weight, recorded_at) VALUES (?,?,?)",
                (pid, weight, _now()),
            )
        self._audit("add_participant", {"id": pid, "name": name})
        self.conn.commit()
        row = dict(self.conn.execute("SELECT * FROM participant WHERE id=?", (pid,)).fetchone())
        row["duplicate_warning"] = warning
        return row

    def update_participant(self, pid: int, data: dict) -> dict:
        prev = self.conn.execute("SELECT * FROM participant WHERE id=?", (pid,)).fetchone()
        if not prev:
            raise KeyError("Участник не найден")
        prev_d = dict(prev)
        name = normalize_name(data.get("name", prev["name"]))
        org = normalize_org(data.get("organization", prev["organization"]))
        rank = normalize_rank(data.get("rank", prev["rank"]))
        year = data.get("birth_year", prev["birth_year"])
        year = int(year) if year not in (None, "") else None
        coach = (data.get("coach", prev["coach"]) or "").strip()
        weight = parse_weight(data.get("weight")) if "weight" in data else prev["weight"]
        status = data.get("status", prev["status"])
        draw = data.get("draw_number", prev["draw_number"])
        draw = int(draw) if draw not in (None, "") else None
        warning = self._dup_warning(name, year, exclude_id=pid)
        self.conn.execute(
            """UPDATE participant SET name=?, organization=?, rank=?, birth_year=?, coach=?,
               weight=?, status=?, draw_number=? WHERE id=?""",
            (name, org, rank, year, coach, weight, status, draw, pid),
        )
        if "weight" in data and weight != prev["weight"] and weight is not None:
            self.conn.execute(
                "INSERT INTO weight_history (participant_id, weight, recorded_at) VALUES (?,?,?)",
                (pid, weight, _now()),
            )
            if status == "заявлен":
                self.conn.execute("UPDATE participant SET status='взвешен' WHERE id=?", (pid,))
        self._audit("update_participant", {"id": pid, "before": prev_d})
        self.conn.commit()
        row = dict(self.conn.execute("SELECT * FROM participant WHERE id=?", (pid,)).fetchone())
        row["duplicate_warning"] = warning
        return row

    def delete_participant(self, pid: int) -> None:
        prev = self.conn.execute("SELECT * FROM participant WHERE id=?", (pid,)).fetchone()
        if not prev:
            return
        self.conn.execute("DELETE FROM participant WHERE id=?", (pid,))
        self._audit("delete_participant", {"before": dict(prev)})
        self.conn.commit()

    def weigh_in(self, pid: int, weight_raw, status: str | None = None) -> dict:
        weight = parse_weight(weight_raw)
        if weight is None:
            raise ValueError("Нужен вес")
        prev = dict(self.conn.execute("SELECT * FROM participant WHERE id=?", (pid,)).fetchone())
        st = status or ("допущен" if prev["status"] in {"заявлен", "взвешен", "допущен"} else prev["status"])
        self.conn.execute("UPDATE participant SET weight=?, status=? WHERE id=?", (weight, st, pid))
        self.conn.execute(
            "INSERT INTO weight_history (participant_id, weight, recorded_at) VALUES (?,?,?)",
            (pid, weight, _now()),
        )
        self._audit("weigh_in", {"id": pid, "before": prev})
        self.conn.commit()
        return dict(self.conn.execute("SELECT * FROM participant WHERE id=?", (pid,)).fetchone())

    def weight_history(self, pid: int) -> list[dict]:
        rows = self.conn.execute(
            "SELECT * FROM weight_history WHERE participant_id=? ORDER BY recorded_at",
            (pid,),
        ).fetchall()
        return [dict(r) for r in rows]

    def _participants_models(self) -> list[Participant]:
        out = []
        for r in self.list_participants():
            out.append(
                Participant(
                    id=r["id"],
                    name=r["name"],
                    organization=r["organization"],
                    rank=r["rank"] or "",
                    birth_year=r["birth_year"],
                    coach=r["coach"] or "",
                    weight=r["weight"],
                    status=r["status"],
                    draw_number=r["draw_number"],
                )
            )
        return out

    # --- classify / draw / brackets ---

    def classify(self) -> dict:
        snapshot = self._snapshot_brackets()
        groups = self.list_age_groups()
        divs = self.list_divisions()
        weights = self.list_weights()
        parts = self._participants_models()
        buckets, unplaced = classify_all(parts, groups, divs, weights)
        tid = self.tid()
        self.conn.execute("DELETE FROM placement WHERE category_id IN (SELECT id FROM category WHERE tournament_id=?)", (tid,))
        self.conn.execute("DELETE FROM bout WHERE tournament_id=?", (tid,))
        self.conn.execute("DELETE FROM category_entry WHERE category_id IN (SELECT id FROM category WHERE tournament_id=?)", (tid,))
        self.conn.execute("DELETE FROM category WHERE tournament_id=?", (tid,))
        created = []
        t = self.get_tournament()
        bronze = bool(t["bronze_bout"])
        for key, plist in buckets.items():
            cur = self.conn.execute(
                """INSERT INTO category (tournament_id, age_group_id, division_id, weight_class_id, drawn_at)
                   VALUES (?,?,?,?,?)""",
                (tid, key.age_group_id, key.division_id, key.weight_class_id, _now()),
            )
            cid = cur.lastrowid
            assigned = assign_control_numbers(plist)
            for pid, ctrl in assigned:
                self.conn.execute(
                    "INSERT INTO category_entry (category_id, participant_id, control_number) VALUES (?,?,?)",
                    (cid, pid, ctrl),
                )
            n = len(assigned)
            bracket = build_bracket(n, bronze_bout=bronze)
            self._write_bracket(cid, bracket)
            created.append(self._category_dict(cid))
        self._renumber_bouts()
        self._audit("classify", {"before": snapshot})
        self.conn.commit()
        return {
            "categories": created,
            "unplaced": [
                {
                    "participant_id": u.participant_id,
                    "reason": u.reason,
                    "participant": _row(
                        self.conn.execute("SELECT * FROM participant WHERE id=?", (u.participant_id,)).fetchone()
                    ),
                }
                for u in unplaced
            ],
        }

    def list_categories(self) -> list[dict]:
        rows = self.conn.execute(
            """SELECT c.*, ag.label AS age_label, d.code AS division_code,
                      w.label AS weight_label, w.limit_kg,
                      (SELECT COUNT(*) FROM category_entry e WHERE e.category_id=c.id) AS n
               FROM category c
               JOIN age_group ag ON ag.id=c.age_group_id
               JOIN division d ON d.id=c.division_id
               JOIN weight_class w ON w.id=c.weight_class_id
               WHERE c.tournament_id=?
               ORDER BY ag.sort_order, d.sort_order, w.limit_kg""",
            (self.tid(),),
        ).fetchall()
        return [self._decorate_category(dict(r)) for r in rows]

    def _decorate_category(self, row: dict) -> dict:
        row["bracket_title"] = bracket_kind_ru(row.get("bracket_kind"))
        return row

    def _category_dict(self, cid: int) -> dict:
        return self._decorate_category(dict(
            self.conn.execute(
                """SELECT c.*, ag.label AS age_label, d.code AS division_code,
                          w.label AS weight_label, w.limit_kg,
                          (SELECT COUNT(*) FROM category_entry e WHERE e.category_id=c.id) AS n
                   FROM category c
                   JOIN age_group ag ON ag.id=c.age_group_id
                   JOIN division d ON d.id=c.division_id
                   JOIN weight_class w ON w.id=c.weight_class_id
                   WHERE c.id=?""",
                (cid,),
            ).fetchone()
        ))

    def category_detail(self, cid: int) -> dict:
        cat = self._category_dict(cid)
        entries = [
            dict(r)
            for r in self.conn.execute(
                """SELECT e.*, p.name, p.organization, p.rank, p.birth_year, p.coach, p.weight, p.draw_number
                   FROM category_entry e JOIN participant p ON p.id=e.participant_id
                   WHERE e.category_id=? ORDER BY e.control_number""",
                (cid,),
            ).fetchall()
        ]
        bouts = [
            dict(r)
            for r in self.conn.execute(
                "SELECT * FROM bout WHERE category_id=? ORDER BY scheduled_order, bout_no, id",
                (cid,),
            ).fetchall()
        ]
        self._hydrate_bouts(bouts)
        places = [
            dict(r)
            for r in self.conn.execute(
                """SELECT pl.*, p.name, p.organization, p.rank, p.birth_year, p.coach
                   FROM placement pl JOIN participant p ON p.id=pl.participant_id
                   WHERE pl.category_id=? ORDER BY pl.place, p.name""",
                (cid,),
            ).fetchall()
        ]
        return {"category": cat, "entries": entries, "bouts": bouts, "placements": places}

    def redraw(self, cid: int, seed: int | None = None) -> dict:
        snapshot = self.category_detail(cid)
        ids = [
            r["participant_id"]
            for r in self.conn.execute(
                "SELECT participant_id FROM category_entry WHERE category_id=? ORDER BY control_number",
                (cid,),
            ).fetchall()
        ]
        assigned, used_seed = redraw_control_numbers(ids, seed=seed)
        assigned.sort(key=lambda x: x[1])
        self.conn.execute("DELETE FROM placement WHERE category_id=?", (cid,))
        self.conn.execute("DELETE FROM bout WHERE category_id=?", (cid,))
        self.conn.execute("DELETE FROM category_entry WHERE category_id=?", (cid,))
        for pid, ctrl in assigned:
            self.conn.execute(
                "INSERT INTO category_entry (category_id, participant_id, control_number) VALUES (?,?,?)",
                (cid, pid, ctrl),
            )
        t = self.get_tournament()
        bracket = build_bracket(len(assigned), bronze_bout=bool(t["bronze_bout"]))
        self._write_bracket(cid, bracket)
        self.conn.execute("UPDATE category SET drawn_at=? WHERE id=?", (_now(), cid))
        self.conn.execute(
            "INSERT INTO draw_log (category_id, method, seed, created_at, payload) VALUES (?,?,?,?,?)",
            (cid, "redraw", used_seed, _now(), json.dumps({"pairs": assigned})),
        )
        self._renumber_bouts()
        self._audit("redraw", {"category_id": cid, "before": snapshot, "seed": used_seed})
        self.conn.commit()
        return self.category_detail(cid)

    def manual_order(self, cid: int, participant_ids: list[int]) -> dict:
        snapshot = self.category_detail(cid)
        if sorted(participant_ids) != sorted(
            [r["participant_id"] for r in self.conn.execute("SELECT participant_id FROM category_entry WHERE category_id=?", (cid,))]
        ):
            raise ValueError("Список участников не совпадает с категорией")
        self.conn.execute("DELETE FROM placement WHERE category_id=?", (cid,))
        self.conn.execute("DELETE FROM bout WHERE category_id=?", (cid,))
        self.conn.execute("DELETE FROM category_entry WHERE category_id=?", (cid,))
        for i, pid in enumerate(participant_ids, start=1):
            self.conn.execute(
                "INSERT INTO category_entry (category_id, participant_id, control_number) VALUES (?,?,?)",
                (cid, pid, i),
            )
        t = self.get_tournament()
        bracket = build_bracket(len(participant_ids), bronze_bout=bool(t["bronze_bout"]))
        self._write_bracket(cid, bracket)
        self.conn.execute(
            "INSERT INTO draw_log (category_id, method, seed, created_at, payload) VALUES (?,?,?,?,?)",
            (cid, "manual", None, _now(), json.dumps({"ids": participant_ids})),
        )
        self._renumber_bouts()
        self._audit("manual_order", {"category_id": cid, "before": snapshot})
        self.conn.commit()
        return self.category_detail(cid)

    def _write_bracket(self, cid: int, bracket: Bracket) -> None:
        tid = self.tid()
        ctrl_to_entry = {
            r["control_number"]: r["id"]
            for r in self.conn.execute("SELECT id, control_number FROM category_entry WHERE category_id=?", (cid,))
        }
        self.conn.execute("UPDATE category SET bracket_kind=? WHERE id=?", (bracket.kind, cid))
        for m in bracket.matches:
            self.conn.execute(
                """INSERT INTO bout
                   (tournament_id, category_id, match_key, round_code, slot, blue_entry_id, red_entry_id,
                    winner_entry_id, is_bye, source_blue, source_red)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    tid,
                    cid,
                    m.key,
                    m.round_code,
                    m.slot,
                    ctrl_to_entry.get(m.blue_ctrl) if m.blue_ctrl else None,
                    ctrl_to_entry.get(m.red_ctrl) if m.red_ctrl else None,
                    ctrl_to_entry.get(m.winner_ctrl) if m.winner_ctrl else None,
                    1 if m.is_bye else 0,
                    m.source_blue,
                    m.source_red,
                ),
            )
        if bracket.kind == "walkover":
            self._recalc_category_places(cid)

    def _bracket_from_db(self, cid: int) -> tuple[Bracket, dict[int, int], dict[int, int]]:
        n = self.conn.execute("SELECT COUNT(*) FROM category_entry WHERE category_id=?", (cid,)).fetchone()[0]
        t = self.get_tournament()
        bracket = build_bracket(n, bronze_bout=bool(t["bronze_bout"]))
        entry_to_ctrl = {
            r["id"]: r["control_number"]
            for r in self.conn.execute("SELECT id, control_number FROM category_entry WHERE category_id=?", (cid,))
        }
        ctrl_to_entry = {v: k for k, v in entry_to_ctrl.items()}
        rows = self.conn.execute("SELECT * FROM bout WHERE category_id=?", (cid,)).fetchall()
        by_key = {m.key: m for m in bracket.matches}
        for r in rows:
            m = by_key.get(r["match_key"])
            if not m:
                continue
            if r["winner_entry_id"] and not m.is_bye:
                m.winner_ctrl = entry_to_ctrl.get(r["winner_entry_id"])
        # propagate from stored winners
        from mma_secretary.core.bracket import _propagate

        _propagate(bracket)
        return bracket, entry_to_ctrl, ctrl_to_entry

    def set_result(self, bout_id: int, winner_entry_id: int, method: str | None = None) -> dict:
        bout = self.conn.execute("SELECT * FROM bout WHERE id=?", (bout_id,)).fetchone()
        if not bout:
            raise KeyError("Бой не найден")
        if bout["is_bye"]:
            raise ValueError("Это проход, не бой")
        if not bout["blue_entry_id"] or not bout["red_entry_id"]:
            raise ValueError("Нельзя внести результат, пока не определены оба участника")
        if winner_entry_id not in (bout["blue_entry_id"], bout["red_entry_id"]):
            raise ValueError("Победитель должен быть синим или красным углом")
        snapshot = self.category_detail(bout["category_id"])
        cid = bout["category_id"]
        bracket, entry_to_ctrl, ctrl_to_entry = self._bracket_from_db(cid)
        apply_winner(bracket, bout["match_key"], entry_to_ctrl[winner_entry_id])
        self._sync_winners(cid, bracket, ctrl_to_entry)
        self.conn.execute("UPDATE bout SET method=? WHERE id=?", (method, bout_id))
        self._recalc_category_places(cid)
        self._audit("set_result", {"bout_id": bout_id, "before": snapshot})
        self.conn.commit()
        return dict(self.conn.execute("SELECT * FROM bout WHERE id=?", (bout_id,)).fetchone())

    def clear_bout(self, bout_id: int) -> dict:
        bout = self.conn.execute("SELECT * FROM bout WHERE id=?", (bout_id,)).fetchone()
        if not bout:
            raise KeyError("Бой не найден")
        snapshot = self.category_detail(bout["category_id"])
        cid = bout["category_id"]
        bracket, _, ctrl_to_entry = self._bracket_from_db(cid)
        clear_result(bracket, bout["match_key"])
        self._sync_winners(cid, bracket, ctrl_to_entry)
        self.conn.execute("UPDATE bout SET method=NULL WHERE id=?", (bout_id,))
        self._recalc_category_places(cid)
        self._audit("clear_bout", {"bout_id": bout_id, "before": snapshot})
        self.conn.commit()
        return dict(self.conn.execute("SELECT * FROM bout WHERE id=?", (bout_id,)).fetchone())

    def _sync_winners(self, cid: int, bracket: Bracket, ctrl_to_entry: dict[int, int]) -> None:
        for m in bracket.matches:
            self.conn.execute(
                """UPDATE bout SET blue_entry_id=?, red_entry_id=?, winner_entry_id=?
                   WHERE category_id=? AND match_key=?""",
                (
                    ctrl_to_entry.get(m.blue_ctrl) if m.blue_ctrl else None,
                    ctrl_to_entry.get(m.red_ctrl) if m.red_ctrl else None,
                    ctrl_to_entry.get(m.winner_ctrl) if m.winner_ctrl else None,
                    cid,
                    m.key,
                ),
            )

    def schedule_bout(self, bout_id: int, ring: int | None, order: int | None) -> dict:
        self.conn.execute("UPDATE bout SET ring=?, scheduled_order=? WHERE id=?", (ring, order, bout_id))
        self.conn.commit()
        return dict(self.conn.execute("SELECT * FROM bout WHERE id=?", (bout_id,)).fetchone())

    def list_bouts(self, fights_only: bool = True) -> list[dict]:
        q = """SELECT b.*, w.label AS weight_label, ag.label AS age_label, d.code AS division_code
               FROM bout b
               JOIN category c ON c.id=b.category_id
               JOIN weight_class w ON w.id=c.weight_class_id
               JOIN age_group ag ON ag.id=c.age_group_id
               JOIN division d ON d.id=c.division_id
               WHERE b.tournament_id=?"""
        if fights_only:
            q += " AND b.is_bye=0"
        q += " ORDER BY COALESCE(b.scheduled_order, 9999), COALESCE(b.bout_no, 9999), b.id"
        rows = [dict(r) for r in self.conn.execute(q, (self.tid(),)).fetchall()]
        self._hydrate_bouts(rows)
        return rows

    def _hydrate_bouts(self, rows: list[dict]) -> None:
        def fighter(eid):
            if not eid:
                return None
            r = self.conn.execute(
                """SELECT e.id, e.control_number, p.name, p.organization, p.id AS participant_id
                   FROM category_entry e JOIN participant p ON p.id=e.participant_id WHERE e.id=?""",
                (eid,),
            ).fetchone()
            return dict(r) if r else None

        for r in rows:
            r["blue"] = fighter(r.get("blue_entry_id"))
            r["red"] = fighter(r.get("red_entry_id"))
            r["winner"] = fighter(r.get("winner_entry_id"))
            r["round_title"] = round_ru(r.get("round_code"))

    def _renumber_bouts(self) -> None:
        rows = self.conn.execute(
            """SELECT b.id FROM bout b
               JOIN category c ON c.id=b.category_id
               JOIN age_group ag ON ag.id=c.age_group_id
               JOIN division d ON d.id=c.division_id
               JOIN weight_class w ON w.id=c.weight_class_id
               WHERE b.tournament_id=? AND b.is_bye=0
               ORDER BY ag.sort_order, d.sort_order, w.limit_kg,
                        CASE b.round_code
                          WHEN '1/32' THEN 1 WHEN '1/16' THEN 2 WHEN '1/8' THEN 3
                          WHEN '1/4' THEN 4 WHEN 'круг' THEN 4 WHEN '1/2' THEN 5
                          WHEN 'за бронзу' THEN 6 WHEN 'финал' THEN 7 ELSE 8 END,
                        b.slot, b.id""",
            (self.tid(),),
        ).fetchall()
        for i, r in enumerate(rows, start=1):
            self.conn.execute("UPDATE bout SET bout_no=?, scheduled_order=? WHERE id=?", (i, i, r["id"]))

    def _recalc_category_places(self, cid: int) -> None:
        t = self.get_tournament()
        bracket, entry_to_ctrl, ctrl_to_entry = self._bracket_from_db(cid)
        # reload winners already in bracket
        two = bool(t["two_bronzes"])
        places = placements_from_bracket(bracket, two_bronzes=two)
        rules = self.list_point_rules()
        award = bool(t["award_walkover"])
        self.conn.execute("DELETE FROM placement WHERE category_id=?", (cid,))
        ctrl_to_pid = {
            r["control_number"]: r["participant_id"]
            for r in self.conn.execute("SELECT control_number, participant_id FROM category_entry WHERE category_id=?", (cid,))
        }
        for p, pts in apply_points(places, rules):
            if bracket.kind == "walkover" and not award:
                pts = 0
            pid = ctrl_to_pid.get(p.control_number)
            if pid:
                self.conn.execute(
                    "INSERT INTO placement (category_id, participant_id, place, points, tied) VALUES (?,?,?,?,?)",
                    (cid, pid, p.place, pts, 1 if p.tied else 0),
                )

    def recalc_all_places(self) -> None:
        for r in self.conn.execute("SELECT id FROM category WHERE tournament_id=?", (self.tid(),)):
            self._recalc_category_places(r["id"])
        self.conn.commit()

    # --- reports ---

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
        titles = {t: 0 for t in TITLES}
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

    # --- undo / snapshot ---

    def _audit(self, action: str, payload: dict) -> None:
        self.conn.execute(
            "INSERT INTO audit_log (tournament_id, action, payload, created_at, undone) VALUES (?,?,?,?,0)",
            (self.tid(), action, json.dumps(payload, ensure_ascii=False, default=str), _now()),
        )

    def _snapshot_brackets(self) -> dict:
        return {
            "categories": [dict(r) for r in self.conn.execute("SELECT * FROM category WHERE tournament_id=?", (self.tid(),))],
            "entries": [
                dict(r)
                for r in self.conn.execute(
                    "SELECT e.* FROM category_entry e JOIN category c ON c.id=e.category_id WHERE c.tournament_id=?",
                    (self.tid(),),
                )
            ],
            "bouts": [dict(r) for r in self.conn.execute("SELECT * FROM bout WHERE tournament_id=?", (self.tid(),))],
            "placements": [
                dict(r)
                for r in self.conn.execute(
                    "SELECT pl.* FROM placement pl JOIN category c ON c.id=pl.category_id WHERE c.tournament_id=?",
                    (self.tid(),),
                )
            ],
        }

    def undo(self) -> dict:
        row = self.conn.execute(
            "SELECT * FROM audit_log WHERE tournament_id=? AND undone=0 ORDER BY id DESC LIMIT 1",
            (self.tid(),),
        ).fetchone()
        if not row:
            raise ValueError("Нечего отменять")
        payload = json.loads(row["payload"])
        action = row["action"]
        if action in {"set_result", "clear_bout", "redraw", "manual_order"} and "before" in payload:
            self._restore_category(payload["before"])
        elif action == "classify" and "before" in payload:
            self._restore_all_brackets(payload["before"])
        elif action == "update_participant" and "before" in payload:
            b = payload["before"]
            self.conn.execute(
                """UPDATE participant SET name=?, organization=?, rank=?, birth_year=?, coach=?,
                   weight=?, status=?, draw_number=? WHERE id=?""",
                (b["name"], b["organization"], b["rank"], b["birth_year"], b["coach"], b["weight"], b["status"], b["draw_number"], b["id"]),
            )
        elif action == "weigh_in" and "before" in payload:
            b = payload["before"]
            self.conn.execute(
                "UPDATE participant SET weight=?, status=? WHERE id=?",
                (b["weight"], b["status"], b["id"]),
            )
        elif action == "add_participant":
            self.conn.execute("DELETE FROM participant WHERE id=?", (payload["id"],))
        elif action == "delete_participant" and "before" in payload:
            b = payload["before"]
            self.conn.execute(
                """INSERT INTO participant
                   (id, tournament_id, seq, name, organization, rank, birth_year, coach, weight, status, draw_number)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?)""",
                (b["id"], b["tournament_id"], b["seq"], b["name"], b["organization"], b["rank"], b["birth_year"], b["coach"], b["weight"], b["status"], b["draw_number"]),
            )
        else:
            raise ValueError(f"Отмена «{action}» не поддерживается")
        self.conn.execute("UPDATE audit_log SET undone=1 WHERE id=?", (row["id"],))
        self.conn.commit()
        return {"undone": action}

    def _restore_category(self, detail: dict) -> None:
        cat = detail["category"]
        cid = cat["id"]
        self.conn.execute("DELETE FROM placement WHERE category_id=?", (cid,))
        self.conn.execute("DELETE FROM bout WHERE category_id=?", (cid,))
        self.conn.execute("DELETE FROM category_entry WHERE category_id=?", (cid,))
        for e in detail["entries"]:
            self.conn.execute(
                "INSERT INTO category_entry (id, category_id, participant_id, control_number) VALUES (?,?,?,?)",
                (e["id"], e["category_id"], e["participant_id"], e["control_number"]),
            )
        for b in detail["bouts"]:
            self.conn.execute(
                """INSERT INTO bout
                   (id, tournament_id, category_id, match_key, bout_no, round_code, slot,
                    blue_entry_id, red_entry_id, winner_entry_id, method, ring, scheduled_order,
                    is_bye, source_blue, source_red)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    b["id"], b["tournament_id"], b["category_id"], b["match_key"], b.get("bout_no"),
                    b["round_code"], b["slot"], b.get("blue_entry_id"), b.get("red_entry_id"),
                    b.get("winner_entry_id"), b.get("method"), b.get("ring"), b.get("scheduled_order"),
                    b.get("is_bye") or 0, b.get("source_blue"), b.get("source_red"),
                ),
            )
        for p in detail["placements"]:
            self.conn.execute(
                "INSERT INTO placement (id, category_id, participant_id, place, points, tied) VALUES (?,?,?,?,?,?)",
                (p["id"], p["category_id"], p["participant_id"], p["place"], p["points"], p.get("tied") or 0),
            )

    def _restore_all_brackets(self, snap: dict) -> None:
        tid = self.tid()
        self.conn.execute("DELETE FROM placement WHERE category_id IN (SELECT id FROM category WHERE tournament_id=?)", (tid,))
        self.conn.execute("DELETE FROM bout WHERE tournament_id=?", (tid,))
        self.conn.execute("DELETE FROM category_entry WHERE category_id IN (SELECT id FROM category WHERE tournament_id=?)", (tid,))
        self.conn.execute("DELETE FROM category WHERE tournament_id=?", (tid,))
        for c in snap.get("categories", []):
            cols = [k for k in c.keys() if k != "n"]
            self.conn.execute(
                f"INSERT INTO category ({','.join(cols)}) VALUES ({','.join('?'*len(cols))})",
                [c[k] for k in cols],
            )
        for e in snap.get("entries", []):
            self.conn.execute(
                "INSERT INTO category_entry (id, category_id, participant_id, control_number) VALUES (?,?,?,?)",
                (e["id"], e["category_id"], e["participant_id"], e["control_number"]),
            )
        for b in snap.get("bouts", []):
            keys = [
                "id", "tournament_id", "category_id", "match_key", "bout_no", "round_code", "slot",
                "blue_entry_id", "red_entry_id", "winner_entry_id", "method", "ring", "scheduled_order",
                "is_bye", "source_blue", "source_red",
            ]
            self.conn.execute(
                f"INSERT INTO bout ({','.join(keys)}) VALUES ({','.join('?'*len(keys))})",
                [b.get(k) for k in keys],
            )
        for p in snap.get("placements", []):
            self.conn.execute(
                "INSERT INTO placement (id, category_id, participant_id, place, points, tied) VALUES (?,?,?,?,?,?)",
                (p["id"], p["category_id"], p["participant_id"], p["place"], p["points"], p.get("tied") or 0),
            )

    def export_bundle(self) -> dict:
        tid = self.tid()
        return {
            "tournament": self.get_tournament(),
            "age_groups": [dict(r) for r in self.conn.execute("SELECT * FROM age_group WHERE tournament_id=?", (tid,))],
            "divisions": [dict(r) for r in self.conn.execute("SELECT * FROM division WHERE tournament_id=?", (tid,))],
            "weights": [dict(r) for r in self.conn.execute("SELECT * FROM weight_class WHERE tournament_id=?", (tid,))],
            "point_rules": [dict(r) for r in self.conn.execute("SELECT * FROM point_rule WHERE tournament_id=?", (tid,))],
            "participants": self.list_participants(),
            "weight_history": [
                dict(r)
                for r in self.conn.execute(
                    "SELECT h.* FROM weight_history h JOIN participant p ON p.id=h.participant_id WHERE p.tournament_id=?",
                    (tid,),
                )
            ],
            "brackets": self._snapshot_brackets(),
            "team_rep": [dict(r) for r in self.conn.execute("SELECT * FROM team_rep WHERE tournament_id=?", (tid,))],
            "draw_log": [
                dict(r)
                for r in self.conn.execute(
                    "SELECT d.* FROM draw_log d JOIN category c ON c.id=d.category_id WHERE c.tournament_id=?",
                    (tid,),
                )
            ],
        }

    def import_bundle(self, data: dict) -> None:
        tid = self.tid()
        self.conn.execute("DELETE FROM placement")
        self.conn.execute("DELETE FROM bout")
        self.conn.execute("DELETE FROM category_entry")
        self.conn.execute("DELETE FROM category")
        self.conn.execute("DELETE FROM weight_history")
        self.conn.execute("DELETE FROM participant")
        self.conn.execute("DELETE FROM point_rule")
        self.conn.execute("DELETE FROM weight_class")
        self.conn.execute("DELETE FROM division")
        self.conn.execute("DELETE FROM age_group")
        self.conn.execute("DELETE FROM team_rep")
        t = data.get("tournament") or {}
        self.update_tournament({k: t[k] for k in t if k != "id"})
        id_map_ag, id_map_div, id_map_w, id_map_p, id_map_c, id_map_e = {}, {}, {}, {}, {}, {}
        for r in data.get("age_groups", []):
            cur = self.conn.execute(
                "INSERT INTO age_group (tournament_id, label, year_from, year_to, sort_order) VALUES (?,?,?,?,?)",
                (tid, r["label"], r["year_from"], r["year_to"], r.get("sort_order") or 0),
            )
            id_map_ag[r["id"]] = cur.lastrowid
        for r in data.get("divisions", []):
            cur = self.conn.execute(
                "INSERT INTO division (tournament_id, code, sort_order, rank_values) VALUES (?,?,?,?)",
                (tid, r["code"], r.get("sort_order") or 0, r.get("rank_values") or "[]"),
            )
            id_map_div[r["id"]] = cur.lastrowid
        for r in data.get("weights", []):
            cur = self.conn.execute(
                "INSERT INTO weight_class (tournament_id, age_group_id, limit_kg, label, sort_order) VALUES (?,?,?,?,?)",
                (tid, id_map_ag.get(r.get("age_group_id")), r["limit_kg"], r["label"], r.get("sort_order") or 0),
            )
            id_map_w[r["id"]] = cur.lastrowid
        for r in data.get("point_rules", []):
            self.conn.execute(
                "INSERT INTO point_rule (tournament_id, place_from, place_to, points) VALUES (?,?,?,?)",
                (tid, r["place_from"], r["place_to"], r["points"]),
            )
        for r in data.get("participants", []):
            cur = self.conn.execute(
                """INSERT INTO participant (tournament_id, seq, name, organization, rank, birth_year, coach, weight, status, draw_number)
                   VALUES (?,?,?,?,?,?,?,?,?,?)""",
                (tid, r.get("seq"), r["name"], r.get("organization") or "", r.get("rank") or "", r.get("birth_year"), r.get("coach") or "", r.get("weight"), r.get("status") or "заявлен", r.get("draw_number")),
            )
            id_map_p[r["id"]] = cur.lastrowid
        br = data.get("brackets") or {}
        for r in br.get("categories", []):
            cur = self.conn.execute(
                """INSERT INTO category (tournament_id, age_group_id, division_id, weight_class_id, bracket_kind, drawn_at)
                   VALUES (?,?,?,?,?,?)""",
                (tid, id_map_ag[r["age_group_id"]], id_map_div[r["division_id"]], id_map_w[r["weight_class_id"]], r.get("bracket_kind"), r.get("drawn_at")),
            )
            id_map_c[r["id"]] = cur.lastrowid
        for r in br.get("entries", []):
            cur = self.conn.execute(
                "INSERT INTO category_entry (category_id, participant_id, control_number) VALUES (?,?,?)",
                (id_map_c[r["category_id"]], id_map_p[r["participant_id"]], r["control_number"]),
            )
            id_map_e[r["id"]] = cur.lastrowid
        for r in br.get("bouts", []):
            self.conn.execute(
                """INSERT INTO bout (tournament_id, category_id, match_key, bout_no, round_code, slot,
                    blue_entry_id, red_entry_id, winner_entry_id, method, ring, scheduled_order, is_bye, source_blue, source_red)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    tid, id_map_c[r["category_id"]], r["match_key"], r.get("bout_no"), r["round_code"], r.get("slot") or 0,
                    id_map_e.get(r.get("blue_entry_id")), id_map_e.get(r.get("red_entry_id")),
                    id_map_e.get(r.get("winner_entry_id")), r.get("method"), r.get("ring"), r.get("scheduled_order"),
                    r.get("is_bye") or 0, r.get("source_blue"), r.get("source_red"),
                ),
            )
        for r in br.get("placements", []):
            self.conn.execute(
                "INSERT INTO placement (category_id, participant_id, place, points, tied) VALUES (?,?,?,?,?)",
                (id_map_c[r["category_id"]], id_map_p[r["participant_id"]], r["place"], r["points"], r.get("tied") or 0),
            )
        self.conn.commit()

    def seed_defaults(self) -> None:
        if self.list_age_groups():
            return
        self.save_age_group({"label": "2007-2008", "year_from": 2007, "year_to": 2008, "sort_order": 0})
        for i, code in enumerate("АБВГД"):
            self.save_division({"code": code, "sort_order": i})
        for kg in (52.2, 56.7, 61.2, 65.8, 70.3, 77.1, 83.9, 93, 120.2):
            self.save_weight({"limit_kg": kg, "label": format_kg(kg)})
        self.update_tournament(
            {
                "name": "Фестиваль спортивных единоборств",
                "kind": "смешанное боевое единоборство (ММА)",
                "date": "2024-09-14",
                "city": "г. Калининград",
                "chief_referee": "Бохан Е.А.",
                "chief_secretary": "Мамонов В.",
            }
        )
