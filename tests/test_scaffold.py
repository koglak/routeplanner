from datetime import date

from museumdb.scaffold import build_draft
from museumdb.validation import validate_city_dict

TODAY = date(2026, 10, 1)
CITY = {"qid": "Q220", "name": "Rome", "country": "IT"}
VATICAN = {"id": "Q182955", "name": "Vatican Museums", "name_local": "Musei Vaticani",
           "coords": [41.906389, 12.454444], "website": "https://www.museivaticani.va",
           "address": "Viale Vaticano 6", "sitelinks": 80}
BORGHESE = {"id": "Q1", "name": "Borghese Gallery", "name_local": None, "coords": None, "website": None,
            "address": None, "sitelinks": 40}


def test_build_draft_is_a_valid_document():
    draft = build_draft("rome", CITY, [VATICAN, BORGHESE], {}, TODAY)
    validate_city_dict(draft)
    assert draft["city"] == {"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220",
                             "queried_at": "2026-10-01"}


def test_build_draft_ranks_museums_in_given_order():
    draft = build_draft("rome", CITY, [VATICAN, BORGHESE], {}, TODAY)
    assert [(m["id"], m["popularity_rank"]) for m in draft["museums"]] == [("Q182955", 1), ("Q1", 2)]


def test_build_draft_copies_identity_fields_only():
    museum = build_draft("rome", CITY, [VATICAN], {}, TODAY)["museums"][0]
    assert museum == {
        "id": "Q182955", "name": "Vatican Museums", "name_local": "Musei Vaticani", "category": [],
        "popularity_rank": 1, "address": "Viale Vaticano 6", "coords": [41.906389, 12.454444],
        "website": "https://www.museivaticani.va", "user_notes": [],
    }


def test_build_draft_adds_osm_hours_where_found():
    museums = build_draft("rome", CITY, [VATICAN, BORGHESE], {"Q1": "Tu-Su 09:00-19:00"}, TODAY)["museums"]
    assert "volatile" not in museums[0]
    assert museums[1]["volatile"] == {"hours": {"value": "Tu-Su 09:00-19:00", "source": "osm",
                                                "checked": "2026-10-01"}}
