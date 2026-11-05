"""Storage interface and the JSON-file backend.

Swapping backends (SQLite, Postgres) means writing another class with the Store methods;
the CLI and the /muze skill only depend on this interface.
"""
from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import Callable, Protocol

from museumdb.merge import merge_city
from museumdb.models import PLANNING_FIELDS, VOLATILE_FIELDS, City, CityIndexEntry
from museumdb.validation import ValidationError, check_slug, parse_city, validate_city_dict

DEFAULT_MAX_AGE_DAYS = 90


class CityNotFound(LookupError):
    """No stored record for the requested city slug."""


class Store(Protocol):
    def get_city(self, slug: str) -> City | None: ...

    def save_city(self, city: City) -> None:
        """Validate, merge with the stored record and write atomically."""

    def stale_fields(self, slug: str, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> list[tuple[str, str]]:
        """[(museum_id, "volatile.price"), ...] for planning/volatile fields older than max_age_days."""

    def list_cities(self) -> list[CityIndexEntry]: ...


class JsonStore:
    """One JSON file per city under <root>/cities, plus <root>/index.json."""

    def __init__(self, root: Path | str, today: Callable[[], date] = date.today) -> None:
        self.root = Path(root)
        self._today = today

    def get_city(self, slug: str) -> City | None:
        path = self._city_path(slug)
        if not path.exists():
            return None
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as e:
            raise ValidationError(f"{path}: invalid JSON: {e}") from e
        return parse_city(data)

    def save_city(self, city: City) -> None:
        path = self._city_path(city.slug)
        validate_city_dict(city.to_dict())
        merged = merge_city(self.get_city(city.slug), city)
        data = merged.to_dict()
        validate_city_dict(data)
        _atomic_write_json(path, data)
        self._update_index(merged)

    def stale_fields(self, slug: str, max_age_days: int = DEFAULT_MAX_AGE_DAYS) -> list[tuple[str, str]]:
        city = self.get_city(slug)
        if city is None:
            raise CityNotFound(slug)
        today = self._today()
        stale = []
        for museum in city.museums:
            for group, names in (("planning", PLANNING_FIELDS), ("volatile", VOLATILE_FIELDS)):
                values = getattr(museum, group)
                for name in names:
                    value = values.get(name)
                    if value is None or (today - date.fromisoformat(value.checked)).days > max_age_days:
                        stale.append((museum.id, f"{group}.{name}"))
        return stale

    def list_cities(self) -> list[CityIndexEntry]:
        if not self._index_path.exists():
            return []
        return [CityIndexEntry(**e) for e in json.loads(self._index_path.read_text(encoding="utf-8"))]

    @property
    def _index_path(self) -> Path:
        return self.root / "index.json"

    def _city_path(self, slug: str) -> Path:
        check_slug(slug)
        return self.root / "cities" / f"{slug}.json"

    def _update_index(self, city: City) -> None:
        entries = {e.slug: e for e in self.list_cities()}
        entries[city.slug] = CityIndexEntry(
            slug=city.slug,
            name=city.name,
            country=city.country,
            wikidata_id=city.wikidata_id,
            queried_at=city.queried_at,
            museum_count=len(city.museums),
        )
        ordered = sorted(entries.values(), key=lambda e: e.slug)
        _atomic_write_json(self._index_path, [asdict(e) for e in ordered])


def _atomic_write_json(path: Path, data: object) -> None:
    """Write to a temp file in the same directory, then rename over the target."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise
