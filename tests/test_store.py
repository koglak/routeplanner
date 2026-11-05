import copy
import json
from datetime import date

import pytest

from museumdb.models import City, CityIndexEntry
from museumdb.store import CityNotFound, JsonStore
from museumdb.validation import ValidationError

FIELDS = ("planning.busiest", "planning.queue_min", "planning.advance_ticket", "volatile.price", "volatile.hours")
VATICAN_ALL = [("Q182955", f) for f in FIELDS]
BORGHESE_ALL = [("Q999001", f) for f in FIELDS]


def make_store(tmp_path, today=date(2026, 10, 1)):
    return JsonStore(tmp_path, today=lambda: today)


def test_get_missing_returns_none(tmp_path):
    assert make_store(tmp_path).get_city("rome") is None


def test_save_then_get_round_trips(tmp_path, rome_dict):
    store = make_store(tmp_path)
    store.save_city(City.from_dict(rome_dict))
    assert store.get_city("rome").to_dict() == rome_dict


def test_file_layout_and_readable_utf8(tmp_path, rome_dict):
    make_store(tmp_path).save_city(City.from_dict(rome_dict))
    text = (tmp_path / "cities" / "rome.json").read_text(encoding="utf-8")
    assert "Sa–Ça 10:00–13:00" in text  # stored unescaped
    assert json.loads(text)["city"]["slug"] == "rome"


def test_save_recomputes_summary(tmp_path, rome_dict):
    rome_dict["museums"][0]["duration"].update(typical_min_h=99, confidence="low")
    store = make_store(tmp_path)
    store.save_city(City.from_dict(rome_dict))
    d = store.get_city("rome").museums[0].duration
    assert (d.typical_min_h, d.confidence) == (3, "high")


def test_save_merges_with_existing_record(tmp_path, rome_dict):
    store = make_store(tmp_path)
    rome_dict["museums"][0]["user_notes"] = ["Cuma akşamı açık"]
    store.save_city(City.from_dict(rome_dict))
    draft = copy.deepcopy(rome_dict)
    draft["museums"] = draft["museums"][:1]
    draft["museums"][0]["user_notes"] = []
    store.save_city(City.from_dict(draft))
    city = store.get_city("rome")
    assert [m.id for m in city.museums] == ["Q182955", "Q999001"]
    assert city.museums[0].user_notes == ["Cuma akşamı açık"]


def test_index_tracks_saved_cities(tmp_path, rome_dict):
    store = make_store(tmp_path)
    store.save_city(City.from_dict(rome_dict))
    paris = copy.deepcopy(rome_dict)
    paris["city"] = {"slug": "paris", "name": "Paris", "country": "FR", "wikidata_id": "Q90",
                     "queried_at": "2026-10-02"}
    paris["museums"] = paris["museums"][:1]
    store.save_city(City.from_dict(paris))
    entries = store.list_cities()
    assert [(e.slug, e.museum_count) for e in entries] == [("paris", 1), ("rome", 2)]
    assert entries[1] == CityIndexEntry("rome", "Rome", "IT", "Q220", "2026-10-01", 2)
    on_disk = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert on_disk[1] == {"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220",
                          "queried_at": "2026-10-01", "museum_count": 2}


def test_list_cities_empty(tmp_path):
    assert make_store(tmp_path).list_cities() == []


def test_invalid_draft_writes_nothing(tmp_path, rome_dict):
    rome_dict["museums"][0]["duration"]["signals"][0]["source"] = "yelp"
    with pytest.raises(ValidationError, match="yelp"):
        make_store(tmp_path).save_city(City.from_dict(rome_dict))
    assert list(tmp_path.iterdir()) == []


def test_failed_write_keeps_old_file_and_no_temp_files(tmp_path, rome_dict, monkeypatch):
    store = make_store(tmp_path)
    store.save_city(City.from_dict(rome_dict))
    path = tmp_path / "cities" / "rome.json"
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("disk full")

    monkeypatch.setattr("museumdb.store.os.replace", boom)
    draft = copy.deepcopy(rome_dict)
    draft["museums"][0]["name"] = "Changed"
    with pytest.raises(OSError, match="disk full"):
        store.save_city(City.from_dict(draft))
    assert path.read_bytes() == before
    assert [p.name for p in path.parent.iterdir()] == ["rome.json"]


@pytest.mark.parametrize("content", ["{not json", '{"schema_version": 1, "city": {}, "museums": []}'])
def test_corrupt_existing_file_blocks_save_and_is_untouched(tmp_path, rome_dict, content):
    path = tmp_path / "cities" / "rome.json"
    path.parent.mkdir(parents=True)
    path.write_text(content, encoding="utf-8")
    store = make_store(tmp_path)
    with pytest.raises(ValidationError):
        store.get_city("rome")
    with pytest.raises(ValidationError):
        store.save_city(City.from_dict(rome_dict))
    assert path.read_text(encoding="utf-8") == content


def test_bad_slug_rejected_and_nothing_written(tmp_path, rome_dict):
    store = make_store(tmp_path)
    with pytest.raises(ValidationError, match="invalid slug"):
        store.get_city("../etc")
    rome_dict["city"]["slug"] = "../etc"
    with pytest.raises(ValidationError, match="invalid slug"):
        store.save_city(City.from_dict(rome_dict))
    assert list(tmp_path.iterdir()) == []


def test_fields_exactly_90_days_old_are_fresh(tmp_path, rome_dict):
    make_store(tmp_path).save_city(City.from_dict(rome_dict))
    # Borghese has no planning/volatile at all: never checked, so always stale.
    assert make_store(tmp_path, today=date(2026, 12, 30)).stale_fields("rome") == BORGHESE_ALL


def test_fields_older_than_90_days_are_stale(tmp_path, rome_dict):
    make_store(tmp_path).save_city(City.from_dict(rome_dict))
    assert make_store(tmp_path, today=date(2026, 12, 31)).stale_fields("rome") == VATICAN_ALL + BORGHESE_ALL


def test_custom_max_age(tmp_path, rome_dict):
    make_store(tmp_path).save_city(City.from_dict(rome_dict))
    store = make_store(tmp_path, today=date(2026, 10, 11))
    assert store.stale_fields("rome", max_age_days=5) == VATICAN_ALL + BORGHESE_ALL


def test_checked_but_not_found_value_is_not_stale(tmp_path, rome_dict):
    rome_dict["museums"][1]["volatile"]["price"] = {"value": None, "source": None, "checked": "2026-10-01"}
    store = make_store(tmp_path)
    store.save_city(City.from_dict(rome_dict))
    assert store.stale_fields("rome") == [x for x in BORGHESE_ALL if x[1] != "volatile.price"]


def test_stale_unknown_city_raises(tmp_path):
    with pytest.raises(CityNotFound):
        make_store(tmp_path).stale_fields("rome")
