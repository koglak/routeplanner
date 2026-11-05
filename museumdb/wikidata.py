"""Wikidata and OpenStreetMap lookups used to build city drafts.

Every function takes a `fetch(url) -> parsed JSON` callable so tests can answer without a network.
"""
from __future__ import annotations

import json
import re
import unicodedata
from typing import Callable
from urllib.error import URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

Fetch = Callable[[str], object]

SEARCH_URL = "https://www.wikidata.org/w/api.php"
SPARQL_URL = "https://query.wikidata.org/sparql"
OVERPASS_URL = "https://overpass-api.de/api/interpreter"
USER_AGENT = "travelkardi-museumdb/0.1 (https://github.com/hakansuluoglu/travelkardi)"
TIMEOUT_S = 60
OSM_RADIUS_M = 500
ENTITY_PREFIX = "http://www.wikidata.org/entity/"
QID_RE = re.compile(r"^Q[0-9]+$")
POINT_RE = re.compile(r"^Point\(([-0-9.eE]+) ([-0-9.eE]+)\)$")

MUSEUM_FIELDS = """
  OPTIONAL { ?m wdt:P625 ?coord . }
  OPTIONAL { ?m wdt:P856 ?website . }
  OPTIONAL { ?m wdt:P1705 ?local . }
  OPTIONAL { ?m wdt:P6375 ?address . }
  OPTIONAL { ?m wikibase:sitelinks ?sitelinks . }
  SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
"""
MUSEUM_SELECT = ("SELECT ?m ?mLabel (SAMPLE(?local) AS ?local) (SAMPLE(?coord) AS ?coord) "
                 "(SAMPLE(?website) AS ?website) (SAMPLE(?address) AS ?address) ?sitelinks")
MUSEUM_GROUP = "GROUP BY ?m ?mLabel ?sitelinks"


class FetchError(RuntimeError):
    """A remote service failed or timed out."""


def http_fetch(url: str) -> object:
    request = Request(url, headers={"User-Agent": USER_AGENT, "Accept": "application/json"})
    try:
        with urlopen(request, timeout=TIMEOUT_S) as response:
            return json.load(response)
    except (URLError, TimeoutError, json.JSONDecodeError) as e:
        raise FetchError(f"{url.split('?')[0]}: {e}") from e


def slugify(name: str) -> str:
    ascii_name = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", ascii_name.lower()).strip("-")


def resolve_city(name: str, fetch: Fetch) -> list[dict]:
    """Search results that are human settlements, with slug and ISO country code."""
    hits = _search(name, fetch)
    if not hits:
        return []
    rows = _sparql(f"""
SELECT ?item (SAMPLE(?iso) AS ?iso) ?settlement WHERE {{
  VALUES ?item {{ {_values(h["id"] for h in hits)} }}
  OPTIONAL {{ ?item wdt:P17/wdt:P297 ?iso . }}
  BIND(EXISTS {{ ?item wdt:P31/wdt:P279* wd:Q486972 . }} AS ?settlement)
}} GROUP BY ?item ?settlement""", fetch)
    info = {_qid(r["item"]): r for r in rows}
    cities = []
    for hit in hits:
        row = info.get(hit["id"])
        if row is None or _value(row, "settlement") != "true":
            continue
        cities.append({
            "qid": hit["id"],
            "name": hit.get("label", hit["id"]),
            "description": hit.get("description"),
            "slug": slugify(hit.get("label", "")),
            "country": _value(row, "iso"),
        })
    return cities


def city_details(qid: str, fetch: Fetch) -> dict:
    rows = _sparql(f"""
SELECT ?item ?itemLabel (SAMPLE(?iso) AS ?iso) WHERE {{
  VALUES ?item {{ wd:{qid} }}
  OPTIONAL {{ ?item wdt:P17/wdt:P297 ?iso . }}
  SERVICE wikibase:label {{ bd:serviceParam wikibase:language "en" . }}
}} GROUP BY ?item ?itemLabel""", fetch)
    if not rows:
        raise LookupError(f"no Wikidata item {qid}")
    row = rows[0]
    return {"qid": qid, "name": _value(row, "itemLabel"), "country": _value(row, "iso")}


def museum_candidates(city_qid: str, fetch: Fetch, limit: int = 40) -> list[dict]:
    """Museums located in the city, most Wikipedia sitelinks first.

    The transitive location query can time out for big cities; then only direct location is used.
    """
    try:
        return _museums_in(city_qid, "wdt:P131*", limit, fetch)
    except FetchError:
        return _museums_in(city_qid, "wdt:P131", limit, fetch)


def museum_details(qids: list[str], fetch: Fetch) -> list[dict]:
    """Identity fields for the given museums, in the given order; unknown ids are left out."""
    rows = _sparql(f"""
{MUSEUM_SELECT} WHERE {{
  VALUES ?m {{ {_values(qids)} }}
{MUSEUM_FIELDS}}} {MUSEUM_GROUP}""", fetch)
    by_id = {m["id"]: m for m in _parse_museums(rows)}
    return [by_id[q] for q in qids if q in by_id]


def lookup_museum(name: str, fetch: Fetch) -> list[dict]:
    """Museums matching a name, for ones the city query misses (e.g. Vatican Museums for Rome)."""
    hits = _search(name, fetch)
    return museum_details([h["id"] for h in hits], fetch) if hits else []


def osm_hours(museums: list[dict], fetch: Fetch) -> dict[str, str]:
    """{qid: opening_hours} for OSM objects tagged with a museum's Wikidata id near its coordinates.

    The tag filter must come first so Overpass uses its tag index; area-first queries time out.
    """
    located = [m for m in museums if m.get("coords")]
    if not located:
        return {}
    parts = "".join(
        f'nwr["wikidata"="{m["id"]}"](around:{OSM_RADIUS_M},{m["coords"][0]},{m["coords"][1]});' for m in located
    )
    data = fetch(f"{OVERPASS_URL}?{urlencode({'data': f'[out:json][timeout:60];({parts});out tags;'})}")
    wanted = {m["id"] for m in located}
    hours = {}
    for element in data.get("elements", []):
        tags = element.get("tags", {})
        if tags.get("wikidata") in wanted and tags.get("opening_hours"):
            hours.setdefault(tags["wikidata"], tags["opening_hours"])
    return hours


def _museums_in(city_qid: str, location_path: str, limit: int, fetch: Fetch) -> list[dict]:
    # On a path, walking from the museum up the location chain ("forward") is the order that finishes in time.
    hint = ' hint:Prior hint:gearing "forward" .' if location_path.endswith("*") else ""
    rows = _sparql(f"""
{MUSEUM_SELECT} WHERE {{
  ?m {location_path} wd:{city_qid} .{hint}
  ?m wdt:P31/wdt:P279* wd:Q33506 .
{MUSEUM_FIELDS}}} {MUSEUM_GROUP} ORDER BY DESC(?sitelinks) LIMIT {limit}""", fetch)
    return _parse_museums(rows)


def _parse_museums(rows: list[dict]) -> list[dict]:
    museums = {}
    for row in rows:
        qid = _qid(row["m"])
        if qid in museums:
            continue
        sitelinks = _value(row, "sitelinks")
        museums[qid] = {
            "id": qid,
            "name": _value(row, "mLabel") or qid,
            "name_local": _value(row, "local"),
            "coords": _coords(_value(row, "coord")),
            "website": _value(row, "website"),
            "address": _value(row, "address"),
            "sitelinks": int(sitelinks) if sitelinks is not None else 0,
        }
    return list(museums.values())


def _search(name: str, fetch: Fetch) -> list[dict]:
    params = {"action": "wbsearchentities", "search": name, "language": "en", "type": "item",
              "format": "json", "limit": 7}
    return fetch(f"{SEARCH_URL}?{urlencode(params)}").get("search", [])


def _sparql(query: str, fetch: Fetch) -> list[dict]:
    return fetch(f"{SPARQL_URL}?{urlencode({'format': 'json', 'query': query})}")["results"]["bindings"]


def _values(qids) -> str:
    return " ".join(f"wd:{q}" for q in qids)


def _value(row: dict, key: str) -> str | None:
    cell = row.get(key)
    return cell["value"] if cell else None


def _qid(cell: dict) -> str:
    return cell["value"].removeprefix(ENTITY_PREFIX)


def _coords(point: str | None) -> list[float] | None:
    """WKT 'Point(lon lat)' -> [lat, lon]."""
    match = POINT_RE.match(point) if point else None
    return [float(match.group(2)), float(match.group(1))] if match else None
