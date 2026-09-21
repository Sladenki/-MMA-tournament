BRACKET_KIND_RU = {
    "empty": "пусто",
    "walkover": "без боя",
    "final": "финал",
    "round_robin": "круговая",
    "single_elim": "олимпийская",
}

ROUND_RU = {
    "авто": "без боя",
    "без боя": "без боя",
    "круг": "круг",
    "1/32": "1/32 финала",
    "1/16": "1/16 финала",
    "1/8": "1/8 финала",
    "1/4": "1/4 финала",
    "1/2": "1/2 финала",
    "финал": "финал",
    "за бронзу": "за бронзу",
}


def bracket_kind_ru(kind: str | None) -> str:
    if not kind:
        return "—"
    return BRACKET_KIND_RU.get(kind, kind)


def round_ru(code: str | None) -> str:
    if not code:
        return "—"
    return ROUND_RU.get(code, code)
