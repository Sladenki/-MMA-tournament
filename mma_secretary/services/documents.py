from __future__ import annotations

from html import escape

from mma_secretary.core.normalize import format_kg
from mma_secretary.services.engine import TournamentService


def _header(t: dict) -> str:
    return f"""
    <header class="doc-head">
      <div class="doc-title">{escape(t.get("name") or "Турнир")}</div>
      <div class="doc-sub">{escape(t.get("kind") or "")}</div>
      <div class="doc-meta">{escape(str(t.get("date") or ""))} · {escape(t.get("city") or "")}</div>
    </header>
    """


CSS = """
@page { size: A4; margin: 12mm; }
body { font-family: "Times New Roman", Times, serif; color: #111; }
.doc-head { text-align: center; margin-bottom: 12px; }
.doc-title { font-size: 18px; font-weight: 700; text-transform: uppercase; }
.doc-sub { font-size: 13px; }
.doc-meta { font-size: 12px; margin-top: 4px; }
h2 { font-size: 15px; text-align: center; margin: 16px 0 8px; }
table { border-collapse: collapse; width: 100%; font-size: 11px; }
th, td { border: 1px solid #222; padding: 3px 5px; }
th { background: #eee; }
.sig { margin-top: 28px; display: flex; justify-content: space-between; font-size: 12px; }
.page-break { page-break-before: always; }
.blue { color: #123a8a; }
.red { color: #9b1c1c; }
.cert { text-align: center; padding: 40px 20px; border: 8px double #7a1d1d; min-height: 70vh; }
.cert h1 { letter-spacing: .3em; font-size: 28px; color: #7a1d1d; }
.landscape { }
"""


def wrap(title: str, body: str, landscape: bool = False) -> str:
    orient = "landscape" if landscape else ""
    return f"""<!doctype html><html lang="ru"><head><meta charset="utf-8">
    <title>{escape(title)}</title><style>{CSS}</style></head>
    <body class="{orient}">{body}</body></html>"""


def protocol_weigh_in(svc: TournamentService) -> str:
    t = svc.get_tournament()
    rows = "".join(
        f"<tr><td>{p['seq'] or ''}</td><td>{p['draw_number'] or ''}</td><td></td>"
        f"<td>{escape(p['name'])}</td><td>{escape(p['organization'] or '')}</td>"
        f"<td>{escape(p['rank'] or '')}</td><td>{p['birth_year'] or ''}</td>"
        f"<td>{escape(p['coach'] or '')}</td>"
        f"<td>{format_kg(p['weight']) if p['weight'] is not None else ''}</td></tr>"
        for p in svc.list_participants("team")
    )
    body = _header(t) + f"""
    <h2>Протокол взвешивания и жеребьёвки</h2>
    <table>
      <tr><th>№</th><th>Жребий</th><th>Контр.</th><th>Фамилия, имя</th>
      <th>Город, организация</th><th>Разряд</th><th>Год</th><th>Тренер</th><th>Вес</th></tr>
      {rows}
    </table>
    {_sigs(t)}
    """
    return wrap("Протокол взвешивания", body)


def protocol_mandate(svc: TournamentService) -> str:
    t = svc.get_tournament()
    man = svc.mandate()
    head = "".join(f"<th>{escape(w)}</th>" for w in man["weights"])
    rows = ""
    for r in man["rows"]:
        cells = "".join(f"<td>{r['cells'].get(w, 0) or ''}</td>" for w in man["weights"])
        rows += f"<tr><td>{escape(r['organization'])}</td>{cells}<td>{r['total']}</td><td>{escape(r['representative'])}</td></tr>"
    totals = "".join(f"<td>{man['col_totals'].get(w, 0)}</td>" for w in man["weights"])
    titles = "".join(f"<tr><td>{escape(k)}</td><td>{v}</td></tr>" for k, v in man["titles"].items())
    body = _header(t) + f"""
    <h2>Протокол мандатной комиссии</h2>
    <table>
      <tr><th>Организация</th>{head}<th>Итого</th><th>Представитель</th></tr>
      {rows}
      <tr><th>Итого</th>{totals}<th>{man['grand_total']}</th><th></th></tr>
    </table>
    <h2>Участники по званиям</h2>
    <table><tr><th>Звание / разряд</th><th>Число</th></tr>{titles}</table>
    {_sigs(t)}
    """
    return wrap("Мандатная комиссия", body)


def pair_list(svc: TournamentService) -> str:
    t = svc.get_tournament()
    first_rounds = {"1/32", "1/16", "1/8", "1/4", "круг", "финал"}
    rows = ""
    for b in svc.list_bouts():
        if b["is_bye"] or not b["blue"] or not b["red"]:
            continue
        if b["round_code"] not in first_rounds and b["round_code"] != "1/2":
            continue
        rows += (
            f"<tr><td>{b['bout_no'] or ''}</td>"
            f"<td class='blue'>{escape(b['blue']['name'])} ({escape(b['blue']['organization'])})</td>"
            f"<td class='red'>{escape(b['red']['name'])} ({escape(b['red']['organization'])})</td>"
            f"<td>{escape(str(b.get('weight_label') or ''))}</td><td>{escape(b['round_code'])}</td></tr>"
        )
    body = _header(t) + f"""
    <h2>Список пар</h2>
    <table><tr><th>№ боя</th><th>Синий угол</th><th>Красный угол</th><th>Категория</th><th>Тур</th></tr>{rows}</table>
    """
    return wrap("Список пар", body)


def corner_list(svc: TournamentService) -> str:
    t = svc.get_tournament()
    rows = ""
    for b in svc.list_bouts():
        if b["is_bye"] or not b["blue"] or not b["red"]:
            continue
        rows += (
            f"<tr><td>{b['bout_no'] or ''}</td>"
            f"<td class='blue'>{escape(b['blue']['name'])}<br><small>{escape(b['blue']['organization'])}</small></td>"
            f"<td class='red'>{escape(b['red']['name'])}<br><small>{escape(b['red']['organization'])}</small></td>"
            f"<td>{escape(str(b.get('weight_label') or ''))}</td>"
            f"<td>{escape(b['round_code'])}</td><td>{b.get('ring') or ''}</td></tr>"
        )
    body = _header(t) + f"""
    <h2>Список боёв по углам</h2>
    <table><tr><th>№</th><th>Синий угол</th><th>Красный угол</th><th>Вес</th><th>Тур</th><th>Ринг</th></tr>{rows}</table>
    """
    return wrap("Бои по углам", body)


def personal_results(svc: TournamentService) -> str:
    t = svc.get_tournament()
    rows = "".join(
        f"<tr><td>{escape(r['age_label'])} {escape(r['division_code'])} {escape(r['weight_label'])}</td>"
        f"<td>{r['place']}</td><td>{escape(r['name'])}</td><td>{r['birth_year'] or ''}</td>"
        f"<td>{escape(r['rank'] or '')}</td><td>{escape(r['organization'])}</td>"
        f"<td>{escape(r['coach'] or '')}</td><td>{r['points']}</td></tr>"
        for r in svc.placements_report()
    )
    body = _header(t) + f"""
    <h2>Протокол результатов личного первенства</h2>
    <table><tr><th>Категория</th><th>Место</th><th>Участник</th><th>Год</th><th>Разряд</th><th>Организация</th><th>Тренер</th><th>Очки</th></tr>
    {rows}</table>{_sigs(t)}
    """
    return wrap("Личное первенство", body)


def team_protocol(svc: TournamentService) -> str:
    t = svc.get_tournament()
    rows = "".join(
        f"<tr><td>{s['place']}</td><td>{escape(s['organization'])}</td><td>{s['points']}</td>"
        f"<td>{escape(s['representative'])}</td></tr>"
        for s in svc.team_report()
    )
    body = _header(t) + f"""
    <h2>Командный протокол</h2>
    <table><tr><th>Место</th><th>Организация</th><th>Очки</th><th>Представитель</th></tr>{rows}</table>
    {_sigs(t)}
    """
    return wrap("Командный протокол", body)


def medalists_html(svc: TournamentService) -> str:
    t = svc.get_tournament()
    rows = "".join(
        f"<tr><td>{escape(r['age_label'])} {escape(r['division_code'])} {escape(r['weight_label'])}</td>"
        f"<td>{r['place']}</td><td>{escape(r['name'])}</td><td>{escape(r['organization'])}</td>"
        f"<td>{escape(r['coach'] or '')}</td></tr>"
        for r in svc.medalists()
    )
    body = _header(t) + f"""
    <h2>Призёры</h2>
    <table><tr><th>Категория</th><th>Место</th><th>ФИО</th><th>Организация</th><th>Тренер</th></tr>{rows}</table>
    """
    return wrap("Призёры", body)


def certificates(svc: TournamentService) -> str:
    t = svc.get_tournament()
    pages = []
    word = {1: "первое", 2: "второе", 3: "третье"}
    for r in svc.medalists():
        pages.append(f"""
        <section class="cert page-break">
          <div class="doc-sub">{escape(t.get("name") or "")}</div>
          <h1>ГРАМОТА</h1>
          <p>награждается</p>
          <p style="font-size:26px;font-weight:700">{escape(r["name"])}</p>
          <p>{escape(r["organization"] or "")}</p>
          <p>за {word.get(r["place"], str(r["place"]))} место</p>
          <p>{escape(r["age_label"])} · {escape(r["division_code"])} · до {escape(r["weight_label"])} кг</p>
          <p style="margin-top:40px">{escape(str(t.get("date") or ""))} · {escape(t.get("city") or "")}</p>
          <p>Главный судья ________________ {escape(t.get("chief_referee") or "")}</p>
        </section>
        """)
    if pages:
        pages[0] = pages[0].replace(" page-break", "", 1)
    return wrap("Грамоты", "".join(pages) or "<p>Нет призёров</p>")


def scorecards(svc: TournamentService) -> str:
    t = svc.get_tournament()
    cards = []
    for b in svc.list_bouts():
        if b["is_bye"] or not b["blue"] or not b["red"]:
            continue
        cards.append(f"""
        <section class="page-break">
          {_header(t)}
          <h2>Судейская записка · бой № {b["bout_no"] or "—"}</h2>
          <table>
            <tr><th>Категория</th><td>{escape(str(b.get("weight_label") or ""))}</td>
                <th>Тур</th><td>{escape(b["round_code"])}</td><th>Ринг</th><td>{b.get("ring") or ""}</td></tr>
          </table>
          <br>
          <table>
            <tr><th style="width:50%" class="blue">Синий угол</th><th class="red">Красный угол</th></tr>
            <tr>
              <td class="blue">{escape(b["blue"]["name"])}<br>{escape(b["blue"]["organization"])}</td>
              <td class="red">{escape(b["red"]["name"])}<br>{escape(b["red"]["organization"])}</td>
            </tr>
            <tr><td>Очки: ________</td><td>Очки: ________</td></tr>
          </table>
          <p>Характер победы: {escape(b.get("method") or "________________")}</p>
          <p>Победитель: {escape((b["winner"] or {}).get("name") or "________________")}</p>
          <p>Рефери ________________　　Арбитр ________________</p>
        </section>
        """)
    if cards:
        cards[0] = cards[0].replace(" page-break", "", 1)
    return wrap("Судейские записки", "".join(cards) or "<p>Нет боёв</p>")


def brackets_html(svc: TournamentService) -> str:
    t = svc.get_tournament()
    parts = [_header(t) + "<h2>Сетки по категориям</h2>"]
    for cat in svc.list_categories():
        if cat["n"] == 0:
            continue
        detail = svc.category_detail(cat["id"])
        svg = bracket_svg(detail)
        parts.append(
            f"<section class='page-break'><h2>{escape(cat['age_label'])} · {escape(cat['division_code'])} · "
            f"до {escape(cat['weight_label'])} кг ({cat['n']})</h2>{svg}</section>"
        )
    if len(parts) > 1:
        parts[1] = parts[1].replace(" page-break", "", 1)
    return wrap("Сетки", "".join(parts), landscape=True)


def full_report(svc: TournamentService) -> str:
    chunks = [
        protocol_mandate(svc),
        team_protocol(svc),
        medalists_html(svc),
        personal_results(svc),
        brackets_html(svc),
    ]
    bodies = []
    for i, html in enumerate(chunks):
        start = html.find("<body")
        start = html.find(">", start) + 1
        end = html.rfind("</body>")
        chunk = html[start:end]
        if i:
            chunk = f"<div class='page-break'></div>{chunk}"
        bodies.append(chunk)
    t = svc.get_tournament()
    return wrap("Итоговый отчёт", "".join(bodies), landscape=False)


def _sigs(t: dict) -> str:
    return f"""
    <div class="sig">
      <div>Главный судья ____________ {escape(t.get("chief_referee") or "")}</div>
      <div>Главный секретарь ____________ {escape(t.get("chief_secretary") or "")}</div>
    </div>
    """


def bracket_svg(detail: dict) -> str:
    entries = {e["id"]: e for e in detail["entries"]}
    fights = [b for b in detail["bouts"] if not b.get("is_bye")]
    n = detail["category"]["n"]
    if n <= 1:
        name = detail["entries"][0]["name"] if detail["entries"] else "—"
        return f"<svg xmlns='http://www.w3.org/2000/svg' width='480' height='80'><text x='20' y='40' font-size='16'>{escape(name)} — 1 место</text></svg>"
    if detail["category"].get("bracket_kind") == "round_robin" or n == 3:
        return _rr_svg(detail, entries)
    return _elim_svg(detail, entries, fights)


def _label(entries: dict, eid) -> str:
    if not eid:
        return "—"
    e = entries.get(eid) or {}
    return f"{e.get('control_number', '')}. {e.get('name', '')}"


def _rr_svg(detail: dict, entries: dict) -> str:
    y = 40
    lines = []
    for b in detail["bouts"]:
        if b.get("is_bye"):
            continue
        blue = _label(entries, b.get("blue_entry_id"))
        red = _label(entries, b.get("red_entry_id"))
        w = ""
        if b.get("winner_entry_id"):
            w = f" → {escape(_label(entries, b['winner_entry_id']))}"
        lines.append(
            f"<text x='20' y='{y}' font-size='14'>Бой {b.get('bout_no') or ''}: {escape(blue)} — {escape(red)}{w}</text>"
        )
        y += 28
    return f"<svg xmlns='http://www.w3.org/2000/svg' width='720' height='{y+20}'>{''.join(lines)}</svg>"


def _elim_svg(detail: dict, entries: dict, fights: list[dict]) -> str:
    rounds: dict[str, list] = {}
    order = ["1/32", "1/16", "1/8", "1/4", "1/2", "финал", "за бронзу"]
    for b in detail["bouts"]:
        rounds.setdefault(b["round_code"], []).append(b)
    cols = [r for r in order if r in rounds]
    if not cols:
        cols = list(rounds.keys())
    col_w, row_h = 220, 52
    width = 40 + len(cols) * col_w
    max_rows = max((len(v) for v in rounds.values()), default=1)
    height = 40 + max_rows * row_h * 2
    parts = [f"<svg xmlns='http://www.w3.org/2000/svg' width='{width}' height='{height}' font-family='Segoe UI, sans-serif'>"]
    for ci, code in enumerate(cols):
        x = 20 + ci * col_w
        parts.append(f"<text x='{x}' y='18' font-size='12' fill='#555'>{escape(code)}</text>")
        items = sorted(rounds[code], key=lambda b: b.get("slot") or 0)
        gap = height / (len(items) + 1)
        for i, b in enumerate(items):
            y = int(gap * (i + 1) - 18)
            blue = escape(_label(entries, b.get("blue_entry_id")))
            red = escape(_label(entries, b.get("red_entry_id")))
            fill = "#fff8f0" if b.get("winner_entry_id") else "#fff"
            parts.append(f"<rect x='{x}' y='{y}' width='200' height='44' rx='4' fill='{fill}' stroke='#333'/>")
            parts.append(f"<text x='{x+6}' y='{y+18}' font-size='11' fill='#123a8a'>{blue}</text>")
            parts.append(f"<text x='{x+6}' y='{y+36}' font-size='11' fill='#9b1c1c'>{red}</text>")
    parts.append("</svg>")
    return "".join(parts)
