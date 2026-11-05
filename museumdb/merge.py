"""Merge an incoming city draft into the stored record (spec section 6)."""
from __future__ import annotations

import copy

from museumdb.models import City, Duration, FieldValue, Museum
from museumdb.synth import synthesize

SCALAR_FIELDS = ("name", "name_local", "popularity_rank", "address", "coords", "website")


def merge_city(existing: City | None, incoming: City) -> City:
    """Return a new City; neither argument is modified. Duration summaries are recomputed."""
    if existing is None:
        result = copy.deepcopy(incoming)
    else:
        result = copy.deepcopy(existing)
        result.name = incoming.name
        result.country = incoming.country or result.country
        result.wikidata_id = incoming.wikidata_id or result.wikidata_id
        result.queried_at = incoming.queried_at
        result.schema_version = incoming.schema_version
        by_id = {m.id: m for m in result.museums}
        for museum in incoming.museums:
            current = by_id.get(museum.id)
            if current is None:
                result.museums.append(copy.deepcopy(museum))
            else:
                _merge_museum(current, museum)
    for museum in result.museums:
        if museum.duration is not None:
            museum.duration = synthesize(museum.duration.signals, museum.duration.notes)
    result.museums.sort(key=lambda m: (m.popularity_rank is None, m.popularity_rank or 0, m.name))
    return result


def _merge_museum(current: Museum, incoming: Museum) -> None:
    for name in SCALAR_FIELDS:
        value = getattr(incoming, name)
        if value is not None:
            setattr(current, name, copy.deepcopy(value))
    if incoming.category:
        current.category = list(incoming.category)
    current.duration = _merge_duration(current.duration, incoming.duration)
    _merge_fields(current.planning, incoming.planning)
    _merge_fields(current.volatile, incoming.volatile)
    # user_notes are hand-written and never touched by a merge.


def _merge_duration(current: Duration | None, incoming: Duration | None) -> Duration | None:
    if incoming is None:
        return current
    if current is None:
        return copy.deepcopy(incoming)
    replaced = {s.source for s in incoming.signals}
    signals = [s for s in current.signals if s.source not in replaced] + copy.deepcopy(incoming.signals)
    notes = list(incoming.notes) if incoming.notes else list(current.notes)
    return Duration(signals=signals, notes=notes)


def _merge_fields(current: dict[str, FieldValue], incoming: dict[str, FieldValue]) -> None:
    for key, new in incoming.items():
        old = current.get(key)
        if new.value is None and old is not None and old.value is not None:
            current[key] = FieldValue(old.value, old.source, new.checked)
        else:
            current[key] = copy.deepcopy(new)
