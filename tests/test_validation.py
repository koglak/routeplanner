import re

import pytest

from museumdb.validation import ValidationError, check_slug, parse_city, validate_city_dict


def _vatican(d):
    return d["museums"][0]


def test_valid_document_passes(rome_dict):
    validate_city_dict(rome_dict)
    assert parse_city(rome_dict).name == "Rome"


def test_draft_without_summary_fields_passes(rome_dict):
    duration = _vatican(rome_dict)["duration"]
    for key in ("typical_min_h", "typical_max_h", "fast_h", "thorough_h", "confidence"):
        del duration[key]
    validate_city_dict(rome_dict)


def test_not_found_field_value_passes(rome_dict):
    _vatican(rome_dict)["volatile"]["price"] = {"value": None, "source": None, "checked": "2026-10-01"}
    validate_city_dict(rome_dict)


@pytest.mark.parametrize("museum_id", ["Q42", "osm:way/123", "osm:node/9", "slug:rome/capitoline-museums"])
def test_accepts_all_id_forms(rome_dict, museum_id):
    _vatican(rome_dict)["id"] = museum_id
    validate_city_dict(rome_dict)


@pytest.mark.parametrize("slug", ["rome", "new-york", "st-petersburg", "x1"])
def test_good_slugs(slug):
    check_slug(slug)


@pytest.mark.parametrize("slug", ["../etc", "Rome", "new york", "new--york", "-rome", "", "köln", "rome/x"])
def test_bad_slugs(slug):
    with pytest.raises(ValidationError, match="invalid slug"):
        check_slug(slug)


@pytest.mark.parametrize(
    "mutate, fragment",
    [
        (lambda d: _vatican(d)["duration"]["signals"][0].update(source="yelp"), "yelp"),
        (lambda d: _vatican(d)["volatile"]["price"].update(checked="01.10.2026"), "01.10.2026"),
        (lambda d: _vatican(d)["volatile"]["price"].update(checked="2026-13-45"), "2026-13-45"),
        (lambda d: _vatican(d).update(id="vatican"), "vatican"),
        (lambda d: _vatican(d).update(coords=[41.9]), "coords"),
        (lambda d: _vatican(d)["duration"].update(confidence="certain"), "certain"),
        (lambda d: _vatican(d)["planning"]["advance_ticket"].update(value="maybe"), "maybe"),
        (lambda d: _vatican(d).update(rating=5), "rating"),
        (lambda d: d.update(schema_version=2), "schema_version"),
        (lambda d: _vatican(d).pop("name"), "name"),
        (lambda d: d["city"].update(slug="../etc"), "slug"),
    ],
)
def test_rejects_invalid_documents(rome_dict, mutate, fragment):
    mutate(rome_dict)
    with pytest.raises(ValidationError, match=re.escape(fragment)):
        validate_city_dict(rome_dict)


def test_rejects_duplicate_museum_ids(rome_dict):
    rome_dict["museums"][1]["id"] = rome_dict["museums"][0]["id"]
    with pytest.raises(ValidationError, match="duplicate museum ids: Q182955"):
        validate_city_dict(rome_dict)
