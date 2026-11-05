"""Plain data classes for the museum duration DB and their JSON (dict) form."""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

SCHEMA_VERSION = 1
SOURCES = ("google", "tripadvisor", "reddit", "blog", "official", "wikidata", "osm")
STRONG_SOURCES = ("google", "tripadvisor")
PLANNING_FIELDS = ("busiest", "queue_min", "advance_ticket")
VOLATILE_FIELDS = ("price", "hours")


@dataclass
class Signal:
    """One raw duration statement from one source, e.g. google: "3–4 h"."""

    source: str
    value: str
    checked: str
    url: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> Signal:
        return cls(source=d["source"], value=d["value"], checked=d["checked"], url=d.get("url"))


@dataclass
class FieldValue:
    """A sourced value; value=None with a checked date means "looked, not found"."""

    value: str | None
    source: str | None
    checked: str

    @classmethod
    def from_dict(cls, d: dict) -> FieldValue:
        return cls(value=d.get("value"), source=d.get("source"), checked=d["checked"])


@dataclass
class Duration:
    """Raw signals plus the summary derived from them by synth.synthesize."""

    signals: list[Signal] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)
    typical_min_h: float | None = None
    typical_max_h: float | None = None
    fast_h: float | None = None
    thorough_h: float | None = None
    confidence: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> Duration:
        return cls(
            signals=[Signal.from_dict(s) for s in d.get("signals", [])],
            notes=list(d.get("notes", [])),
            typical_min_h=d.get("typical_min_h"),
            typical_max_h=d.get("typical_max_h"),
            fast_h=d.get("fast_h"),
            thorough_h=d.get("thorough_h"),
            confidence=d.get("confidence"),
        )


@dataclass
class Museum:
    id: str
    name: str
    name_local: str | None = None
    category: list[str] = field(default_factory=list)
    popularity_rank: int | None = None
    address: str | None = None
    coords: list[float] | None = None  # [lat, lon]
    website: str | None = None
    user_notes: list[str] = field(default_factory=list)
    duration: Duration | None = None
    planning: dict[str, FieldValue] = field(default_factory=dict)
    volatile: dict[str, FieldValue] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict) -> Museum:
        duration = d.get("duration")
        coords = d.get("coords")
        return cls(
            id=d["id"],
            name=d["name"],
            name_local=d.get("name_local"),
            category=list(d.get("category", [])),
            popularity_rank=d.get("popularity_rank"),
            address=d.get("address"),
            coords=list(coords) if coords is not None else None,
            website=d.get("website"),
            user_notes=list(d.get("user_notes", [])),
            duration=Duration.from_dict(duration) if duration is not None else None,
            planning={k: FieldValue.from_dict(v) for k, v in d.get("planning", {}).items()},
            volatile={k: FieldValue.from_dict(v) for k, v in d.get("volatile", {}).items()},
        )


@dataclass
class City:
    slug: str
    name: str
    queried_at: str
    country: str | None = None
    wikidata_id: str | None = None
    museums: list[Museum] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self) -> dict:
        return {
            "schema_version": self.schema_version,
            "city": {
                "slug": self.slug,
                "name": self.name,
                "country": self.country,
                "wikidata_id": self.wikidata_id,
                "queried_at": self.queried_at,
            },
            "museums": [asdict(m) for m in self.museums],
        }

    @classmethod
    def from_dict(cls, d: dict) -> City:
        """Build from the file format. Does not validate; use validation.parse_city for untrusted input."""
        c = d["city"]
        return cls(
            slug=c["slug"],
            name=c["name"],
            queried_at=c["queried_at"],
            country=c.get("country"),
            wikidata_id=c.get("wikidata_id"),
            museums=[Museum.from_dict(m) for m in d.get("museums", [])],
            schema_version=d.get("schema_version", SCHEMA_VERSION),
        )


@dataclass
class CityIndexEntry:
    slug: str
    name: str
    country: str | None
    wikidata_id: str | None
    queried_at: str
    museum_count: int
