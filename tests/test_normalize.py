from mma_secretary.core.normalize import (
    format_kg,
    normalize_name,
    normalize_rank,
    parse_age_bounds,
    parse_weight,
)


def test_name_trim_title_and_drop_patronymic():
    assert normalize_name("  иВАНОВ иван СЕРГЕЕВИЧ ") == "Иванов Иван"


def test_rank_upper():
    assert normalize_rank(" кмс ") == "КМС"


def test_weight_comma_and_dot():
    assert parse_weight("52,2") == 52.2
    assert parse_weight("52.2") == 52.2


def test_age_bounds():
    assert parse_age_bounds("2007-2008") == (2007, 2008)
    assert parse_age_bounds("младше 2010") == (2010, 3000)
    assert parse_age_bounds("2005+") == (2005, 3000)


def test_format_kg():
    assert format_kg(52.2) == "52,2"
    assert format_kg(93.0) == "93"
