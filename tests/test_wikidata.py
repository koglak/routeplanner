from urllib.parse import parse_qs, urlparse

import pytest

from museumdb.wikidata import (
    FetchError,
    city_details,
    lookup_museum,
    museum_candidates,
    museum_details,
    osm_hours,
    resolve_city,
    slugify,
)


def binding(**values):
    """SPARQL JSON binding row: binding(m="http://www.wikidata.org/entity/Q1", mLabel="X")."""
    return {k: {"type": "literal", "value": v} for k, v in values.items()}


def sparql(*rows):
    return {"results": {"bindings": list(rows)}}


def entity(qid):
    return f"http://www.wikidata.org/entity/{qid}"


class FakeFetch:
    """Routes a URL to a handler by host; records every request."""

    def __init__(self, search=None, sparql=None, overpass=None):
        self.handlers = {"www.wikidata.org": search, "query.wikidata.org": sparql, "overpass-api.de": overpass}
        self.calls = []

    def __call__(self, url):
        parsed = urlparse(url)
        params = {k: v[0] for k, v in parse_qs(parsed.query).items()}
        self.calls.append((parsed.netloc, params))
        return self.handlers[parsed.netloc](params)


@pytest.mark.parametrize(
    "name, slug",
    [("Rome", "rome"), ("New York City", "new-york-city"), ("São Paulo", "sao-paulo"),
     ("Saint-Étienne", "saint-etienne"), ("  Rio  de Janeiro ", "rio-de-janeiro")],
)
def test_slugify(name, slug):
    assert slugify(name) == slug


def test_resolve_city_keeps_settlements_with_country_code():
    search = {"search": [
        {"id": "Q90", "label": "Paris", "description": "capital city of France"},
        {"id": "Q830149", "label": "Paris", "description": "city in Texas, United States"},
        {"id": "Q167646", "label": "Paris", "description": "Trojan prince in Greek mythology"},
    ]}
    rows = sparql(
        binding(item=entity("Q90"), iso="FR", settlement="true"),
        binding(item=entity("Q830149"), iso="US", settlement="true"),
        binding(item=entity("Q167646"), settlement="false"),
    )
    fetch = FakeFetch(search=lambda p: search, sparql=lambda p: rows)

    assert resolve_city("Paris", fetch) == [
        {"qid": "Q90", "name": "Paris", "description": "capital city of France", "slug": "paris", "country": "FR"},
        {"qid": "Q830149", "name": "Paris", "description": "city in Texas, United States", "slug": "paris",
         "country": "US"},
    ]
    assert fetch.calls[0][1]["search"] == "Paris"


def test_resolve_city_uses_english_label_for_slug():
    search = {"search": [{"id": "Q365", "label": "Cologne", "description": "city in Germany"}]}
    fetch = FakeFetch(search=lambda p: search,
                      sparql=lambda p: sparql(binding(item=entity("Q365"), iso="DE", settlement="true")))
    assert resolve_city("Köln", fetch)[0]["slug"] == "cologne"


def test_resolve_city_without_matches_skips_sparql():
    fetch = FakeFetch(search=lambda p: {"search": []})
    assert resolve_city("Atlantis", fetch) == []
    assert len(fetch.calls) == 1


def test_museum_candidates_parses_rows_and_flips_coordinates():
    rows = sparql(
        binding(m=entity("Q182955"), mLabel="Vatican Museums", local="Musei Vaticani",
                coord="Point(12.454444 41.906389)", website="https://www.museivaticani.va", sitelinks="80"),
        binding(m=entity("Q12345"), mLabel="Small Museum", sitelinks="3"),
    )
    fetch = FakeFetch(sparql=lambda p: rows)

    assert museum_candidates("Q220", fetch) == [
        {"id": "Q182955", "name": "Vatican Museums", "name_local": "Musei Vaticani",
         "coords": [41.906389, 12.454444], "website": "https://www.museivaticani.va", "address": None,
         "sitelinks": 80},
        {"id": "Q12345", "name": "Small Museum", "name_local": None, "coords": None, "website": None,
         "address": None, "sitelinks": 3},
    ]
    assert "wd:Q220" in fetch.calls[0][1]["query"]


def test_museum_candidates_drops_duplicate_rows():
    rows = sparql(
        binding(m=entity("Q1"), mLabel="A", website="https://a.example", sitelinks="5"),
        binding(m=entity("Q1"), mLabel="A", website="https://a.example/en", sitelinks="5"),
    )
    result = museum_candidates("Q220", FakeFetch(sparql=lambda p: rows))
    assert [(m["id"], m["website"]) for m in result] == [("Q1", "https://a.example")]


def test_museum_candidates_falls_back_to_direct_location_on_timeout():
    def handler(params):
        if "wdt:P131*" in params["query"]:
            raise FetchError("timeout")
        return sparql(binding(m=entity("Q1"), mLabel="A", sitelinks="5"))

    fetch = FakeFetch(sparql=handler)
    assert [m["id"] for m in museum_candidates("Q220", fetch)] == ["Q1"]
    assert len(fetch.calls) == 2


def test_museum_candidates_reraises_when_fallback_fails_too():
    def handler(params):
        raise FetchError("down")

    with pytest.raises(FetchError):
        museum_candidates("Q220", FakeFetch(sparql=handler))


def test_museum_details_keeps_requested_order():
    rows = sparql(
        binding(m=entity("Q2"), mLabel="Second", address="Via Roma 1", sitelinks="1"),
        binding(m=entity("Q1"), mLabel="First", sitelinks="9"),
    )
    fetch = FakeFetch(sparql=lambda p: rows)
    result = museum_details(["Q1", "Q2"], fetch)
    assert [m["id"] for m in result] == ["Q1", "Q2"]
    assert result[1]["address"] == "Via Roma 1"
    assert "wd:Q1 wd:Q2" in fetch.calls[0][1]["query"]


def test_lookup_museum_searches_then_fetches_details():
    search = {"search": [{"id": "Q182955", "label": "Vatican Museums", "description": "art museum"}]}
    rows = sparql(binding(m=entity("Q182955"), mLabel="Vatican Museums", sitelinks="80"))
    fetch = FakeFetch(search=lambda p: search, sparql=lambda p: rows)
    assert [m["id"] for m in lookup_museum("Vatican Museums", fetch)] == ["Q182955"]


def test_lookup_museum_without_matches():
    assert lookup_museum("Nowhere Museum", FakeFetch(search=lambda p: {"search": []})) == []


def test_city_details():
    rows = sparql(binding(item=entity("Q220"), itemLabel="Rome", iso="IT"))
    assert city_details("Q220", FakeFetch(sparql=lambda p: rows)) == {"qid": "Q220", "name": "Rome", "country": "IT"}


def test_city_details_unknown_qid():
    with pytest.raises(LookupError):
        city_details("Q999999999", FakeFetch(sparql=lambda p: sparql()))


def test_osm_hours_maps_wikidata_ids():
    response = {"elements": [
        {"type": "way", "id": 1, "tags": {"wikidata": "Q1", "opening_hours": "Mo-Sa 09:00-19:00"}},
        {"type": "node", "id": 2, "tags": {"wikidata": "Q2"}},
    ]}
    fetch = FakeFetch(overpass=lambda p: response)
    museums = [{"id": "Q1", "coords": [41.9, 12.45]}, {"id": "Q2", "coords": [41.8, 12.5]}]
    assert osm_hours(museums, fetch) == {"Q1": "Mo-Sa 09:00-19:00"}


def test_osm_hours_searches_near_each_museum():
    fetch = FakeFetch(overpass=lambda p: {"elements": []})
    osm_hours([{"id": "Q1", "coords": [41.9, 12.45]}, {"id": "Q2", "coords": None}], fetch)
    query = fetch.calls[0][1]["data"]
    assert 'nwr["wikidata"="Q1"](around:500,41.9,12.45);' in query
    assert "Q2" not in query


def test_osm_hours_without_coordinates_skips_request():
    fetch = FakeFetch()
    assert osm_hours([{"id": "Q1", "coords": None}], fetch) == {}
    assert fetch.calls == []
