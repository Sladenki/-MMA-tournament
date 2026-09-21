from mma_secretary.core.grouping import classify_all, classify_participant
from mma_secretary.core.models import AgeGroup, Division, Participant, WeightClass


GROUPS = [AgeGroup(1, "2007-2008", 2007, 2008)]
DIVS = [Division(1, "А", 0), Division(2, "Б", 1)]
WTS = [WeightClass(1, 52.2, "52,2"), WeightClass(2, 65.8, "65,8"), WeightClass(3, 120.2, "120,2")]


def P(**kw):
    base = dict(id=1, name="Тест", organization="X", rank="", birth_year=2007, coach="", weight=50, status="взвешен")
    base.update(kw)
    return Participant(**base)


def test_empty_rank_goes_to_first_division():
    key, miss = classify_participant(P(rank=""), GROUPS, DIVS, WTS)
    assert miss is None
    assert key.division_id == 1


def test_rank_1_goes_to_second_division():
    key, miss = classify_participant(P(rank="1"), GROUPS, DIVS, WTS)
    assert miss is None
    assert key.division_id == 2


def test_unknown_rank_is_unplaced():
    key, miss = classify_participant(P(rank="Ю1"), GROUPS, DIVS, WTS)
    assert key is None
    assert "не распознан" in miss.reason


def test_overweight_is_unplaced():
    key, miss = classify_participant(P(weight=130), GROUPS, DIVS, WTS)
    assert key is None
    assert "выше верхней" in miss.reason


def test_wrong_year_unplaced():
    key, miss = classify_participant(P(birth_year=2005), GROUPS, DIVS, WTS)
    assert key is None


def test_weight_picks_first_limit():
    key, _ = classify_participant(P(weight=65), GROUPS, DIVS, WTS)
    assert key.weight_class_id == 2


def test_classify_all_does_not_drop_silently():
    people = [P(id=1, weight=None), P(id=2, birth_year=1999, weight=50)]
    buckets, unplaced = classify_all(people, GROUPS, DIVS, WTS)
    assert buckets == {}
    assert len(unplaced) == 2
