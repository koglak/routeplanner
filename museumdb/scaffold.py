"""Draft skeleton from Wikidata identity fields; research fields are left for /muze to fill."""
from __future__ import annotations

from datetime import date

from museumdb.models import SCHEMA_VERSION

IDENTITY_FIELDS = ("name", "name_local", "address", "coords", "website")


def build_draft(slug: str, city: dict, museums: list[dict], hours: dict[str, str], today: date) -> dict:
    """Museums are ranked in the given order; OSM opening hours are added where found."""
    checked = today.isoformat()
    entries = []
    for rank, museum in enumerate(museums, start=1):
        entry = {"id": museum["id"], **{k: museum[k] for k in IDENTITY_FIELDS}}
        entry.update(category=[], popularity_rank=rank, user_notes=[])
        if museum["id"] in hours:
            entry["volatile"] = {"hours": {"value": hours[museum["id"]], "source": "osm", "checked": checked}}
        entries.append(entry)
    return {
        "schema_version": SCHEMA_VERSION,
        "city": {"slug": slug, "name": city["name"], "country": city["country"], "wikidata_id": city["qid"],
                 "queried_at": checked},
        "museums": entries,
    }
