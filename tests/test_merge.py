import copy

from museumdb.merge import merge_city
from museumdb.models import City, FieldValue


def _city(d):
    return City.from_dict(d)


def _merge(existing_dict, incoming_dict):
    return merge_city(_city(existing_dict), _city(incoming_dict))


def test_no_existing_returns_copy_with_recomputed_summary(rome_dict):
    rome_dict["museums"][0]["duration"]["typical_min_h"] = 99
    incoming = _city(rome_dict)
    result = merge_city(None, incoming)
    assert result.museums[0].duration.typical_min_h == 3
    assert incoming.museums[0].duration.typical_min_h == 99  # input untouched


def test_inputs_are_not_mutated(rome_dict):
    existing = _city(rome_dict)
    before = copy.deepcopy(existing)
    inc = copy.deepcopy(rome_dict)
    inc["museums"][0]["volatile"]["price"] = {"value": "€25", "source": "official", "checked": "2027-01-15"}
    merge_city(existing, _city(inc))
    assert existing == before


def test_city_fields_update_but_null_does_not_erase(rome_dict):
    inc = copy.deepcopy(rome_dict)
    inc["city"]["queried_at"] = "2027-01-15"
    inc["city"]["country"] = None
    result = _merge(rome_dict, inc)
    assert result.queried_at == "2027-01-15"
    assert result.country == "IT"


def test_scalar_null_does_not_overwrite_but_value_does(rome_dict):
    inc = copy.deepcopy(rome_dict)
    inc["museums"][0]["address"] = None
    inc["museums"][0]["website"] = "https://new.example"
    inc["museums"][0]["category"] = []
    v = _merge(rome_dict, inc).museums[0]
    assert v.address == "Viale Vaticano, 00165 Roma"
    assert v.website == "https://new.example"
    assert v.category == ["art", "history"]


def test_new_museums_added_and_missing_ones_kept(rome_dict):
    inc = copy.deepcopy(rome_dict)
    inc["museums"] = [{"id": "Q999002", "name": "Capitoline Museums", "popularity_rank": 3}]
    result = _merge(rome_dict, inc)
    assert [m.id for m in result.museums] == ["Q182955", "Q999001", "Q999002"]


def test_museums_sorted_by_rank_unranked_last(rome_dict):
    rome_dict["museums"] = [
        {"id": "Q3", "name": "Unranked"},
        {"id": "Q2", "name": "Second", "popularity_rank": 2},
        {"id": "Q1", "name": "First", "popularity_rank": 1},
    ]
    assert [m.id for m in merge_city(None, _city(rome_dict)).museums] == ["Q1", "Q2", "Q3"]


def test_null_field_keeps_value_but_updates_checked(rome_dict):
    inc = copy.deepcopy(rome_dict)
    inc["museums"][0]["volatile"]["price"] = {"value": None, "source": None, "checked": "2027-01-15"}
    result = _merge(rome_dict, inc)
    assert result.museums[0].volatile["price"] == FieldValue("€20 adult", "official", "2027-01-15")


def test_non_null_field_overwrites(rome_dict):
    inc = copy.deepcopy(rome_dict)
    inc["museums"][0]["volatile"]["price"] = {"value": "€25 adult", "source": "official", "checked": "2027-01-15"}
    result = _merge(rome_dict, inc)
    assert result.museums[0].volatile["price"] == FieldValue("€25 adult", "official", "2027-01-15")


def test_null_field_is_recorded_when_nothing_existed(rome_dict):
    inc = copy.deepcopy(rome_dict)
    inc["museums"][1]["volatile"]["price"] = {"value": None, "source": None, "checked": "2027-01-15"}
    result = _merge(rome_dict, inc)
    assert result.museums[1].volatile["price"] == FieldValue(None, None, "2027-01-15")


def test_signals_replaced_per_source_and_summary_recomputed(rome_dict):
    inc = copy.deepcopy(rome_dict)
    inc["museums"][0]["duration"]["signals"] = [
        {"source": "google", "value": "2-3 h", "checked": "2027-01-15", "url": None}
    ]
    d = _merge(rome_dict, inc).museums[0].duration
    assert sorted((s.source, s.value) for s in d.signals) == [
        ("google", "2-3 h"),
        ("reddit", "~5 h with audio guide"),
        ("tripadvisor", "More than 3 hours"),
    ]
    assert (d.typical_min_h, d.typical_max_h, d.fast_h, d.thorough_h, d.confidence) == (3, 3, 2, 5, "high")


def test_incoming_source_replaces_all_old_signals_of_that_source(rome_dict):
    rome_dict["museums"][0]["duration"]["signals"].append(
        {"source": "reddit", "value": "4 hours", "checked": "2026-10-01", "url": None}
    )
    inc = copy.deepcopy(rome_dict)
    inc["museums"][0]["duration"]["signals"] = [
        {"source": "reddit", "value": "3 hours", "checked": "2027-01-15", "url": None}
    ]
    d = _merge(rome_dict, inc).museums[0].duration
    assert [s.value for s in d.signals if s.source == "reddit"] == ["3 hours"]


def test_null_duration_and_empty_notes_do_not_erase(rome_dict):
    inc = copy.deepcopy(rome_dict)
    inc["museums"][0]["duration"]["notes"] = []
    inc["museums"][1]["duration"] = None
    result = _merge(rome_dict, inc)
    assert result.museums[0].duration.notes == ["Sesli rehberle +1 saat"]
    assert result.museums[1].duration.confidence == "medium"


def test_new_notes_replace_old(rome_dict):
    inc = copy.deepcopy(rome_dict)
    inc["museums"][0]["duration"]["notes"] = ["Sistine Şapeli kuyruğu uzun"]
    assert _merge(rome_dict, inc).museums[0].duration.notes == ["Sistine Şapeli kuyruğu uzun"]


def test_user_notes_never_changed(rome_dict):
    rome_dict["museums"][0]["user_notes"] = ["Pazartesi kapalı mı kontrol et"]
    inc = copy.deepcopy(rome_dict)
    inc["museums"][0]["user_notes"] = ["overwritten?"]
    assert _merge(rome_dict, inc).museums[0].user_notes == ["Pazartesi kapalı mı kontrol et"]
