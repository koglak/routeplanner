# Müze Süre Veritabanı Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** `/muze <şehir> [--yenile]` komutuyla bir şehrin popüler müzelerinde geçirilen süreyi web'den toplayıp kaynaklarıyla birlikte kalıcı JSON dosyalarında biriktiren sistem.

**Architecture:** Web araştırmasını Claude Code skill'i (`.claude/skills/muze/SKILL.md`) yapar; tüm dosya işlemleri ağa hiç çıkmayan, deterministik bir Python paketinden (`museumdb`) geçer. Paket katmanları: `models` (dataclass'lar) → `validation` (JSON Schema) → `synth` (sinyal → özet/güven) → `merge` (birleştirme kuralları) → `store` (`Store` protokolü + `JsonStore`, atomik yazma) → `table` / `cli`. Skill yalnızca CLI'ı çağırır; backend değişimi skill'e dokunmaz.

**Tech Stack:** Python 3.11+ (makinede 3.13), `jsonschema`, `pytest`, setuptools (`pyproject.toml`), proje içi `.venv`.

**Spec:** `docs/superpowers/specs/2026-10-01-museum-duration-db-design.md`

## Global Constraints

- Python 3.11+; çalışma zamanı bağımlılığı yalnızca `jsonschema`, geliştirme bağımlılığı yalnızca `pytest`. Başka bağımlılık yok.
- Python tarafı ağa çıkmaz; deterministik ve test edilebilir.
- Hiçbir değer kaynaksız kaydedilmez; bulunamayan değer `null` kalır. Kayıp alan: `{"value": null, "source": null, "checked": <tarih>}`.
- Kaynak listesi (sabit): `google`, `tripadvisor`, `reddit`, `blog`, `official`, `wikidata`, `osm`. Güçlü kaynaklar: `google`, `tripadvisor`.
- Güven: `high` = en az 2 kaynağın aralıkları örtüşüyor; `medium` = tek güçlü kaynak ya da güçlü kaynaklar örtüşmüyor; `low` = yalnızca `reddit`/`blog`; sinyal yoksa `duration: null`.
- Kimlik: Wikidata ID; yoksa `osm:<type>/<id>`; o da yoksa `slug:<city>/<museum-slug>`.
- Bayatlama: `planning` ve `volatile` altındaki her alanın kendi `checked` tarihi var; 90 günden eskiyse bayat. `duration` yalnızca `--yenile` ile güncellenir.
- `user_notes` elle eklenir; birleştirmede asla ezilmez.
- Dosya düzeni: `data/cities/<slug>.json` (slug İngilizce, ör. `rome`), `data/index.json` (`[{slug, name, country, wikidata_id, queried_at, museum_count}]`).
- `schema_version: 1`.
- Notlar Türkçe; adlar İngilizce + yerel; şehir başına en fazla 15 müze (skill uygular).
- Yazma atomik: doğrulama hatasında veya yarıda kesilmede eski dosya bozulmaz.
- Her commit mesajı şu satırla biter: `Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>` (komutlarda ikinci `-m` olarak verilmiştir).

## Spec'ten bilinçli sapmalar / netleştirmeler

Bunlar spec'in sessiz kaldığı veya uygulamada belirsiz kalan noktalar için alınan kararlardır; Task 10'da spec'e işlenir.

1. `city` nesnesine `slug` alanı eklendi (`save_city(city)` slug'ı bilmek zorunda). CLI `save <slug>` taslakta slug yoksa doldurur, farklıysa reddeder.
2. Spec'teki dosyalara ek olarak `museumdb/validation.py` (şema + slug kontrolü), `museumdb/merge.py` (Bölüm 6 kuralları, saf fonksiyon) ve `museumdb/table.py` (tablo çıktısı) eklendi; her biri tek sorumluluklu.
3. Taslakta hiç olmayan `planning`/`volatile` alanı ("hiç bakılmadı") bayat sayılır.
4. Sinyal var ama hiçbiri ayrıştırılamıyorsa: `duration` sinyalleri saklar, sayısal alanlar ve `confidence` `null` olur; tabloda "veri yok".
5. Özet alanları (`typical_*`, `fast_h`, `thorough_h`, `confidence`) her `save`'de sinyallerden yeniden hesaplanır; taslaktaki değerleri yok sayılır. Hesap: güçlü kaynak varsa tipik aralık onların kesişimi (kesişim yoksa kapsayan aralık), yoksa tüm sinyallerin; `fast_h` = en küçük alt sınır, `thorough_h` = en büyük üst sınır (açık uçluysa alt sınır).
6. Aynı kaynaktan birden çok sinyal olabilir; birleştirmede gelen bir kaynak, o kaynağın eski sinyallerinin **hepsinin** yerini alır.

## Review Focus

1. **Geçersiz/tehlikeli slug** (`../etc`, `Rome`, `new york`, `köln`) → `ValidationError`, CLI çıkış kodu 2, `data/` dışına (ve içine) hiçbir şey yazılmaz. Testler: Task 2, Task 6, Task 8.
2. **Ayrıştırılamayan veya saçma süre metni** (`"half a day"`, `"2h30"`, `"3 people"`, `"15 hours"`) → sinyal saklanır, özete girmez, çökme olmaz; `"2h30"` asla 2–30 saat aralığı olmaz. Testler: Task 3, Task 4.
3. **Aynı müze id'si iki kez / aynı kaynaktan birden çok sinyal** → id tekrarı reddedilir; aynı kaynaklı sinyaller birleştirmede grup olarak yer değiştirir (eski reddit sinyali "artık" kalmaz). Testler: Task 2, Task 5.
4. **Hiç bakılmamış `planning`/`volatile` alanı** (taslakta anahtar yok) → bayat listesinde çıkar; yoksa hiçbir zaman doldurulmaz. `null` değerli ama `checked` tarihli alan ise bayat sayılmaz. Testler: Task 6, Task 8.
5. **Elle düzenlenip bozulmuş mevcut şehir dosyası** (geçersiz JSON veya şemaya uymayan) → `get` ve `save` net bir `ValidationError` verir, dosyaya dokunulmaz (elle yazılmış `user_notes` kaybolmaz). Test: Task 6.

---

## File Structure

```
travelkardi/
  .gitignore                     # .venv, cache'ler
  pyproject.toml                 # paket + bağımlılıklar + pytest ayarı
  .claude/skills/muze/SKILL.md   # /muze komutu: web araştırması + CLI çağrıları
  museumdb/
    __init__.py
    models.py      # City, Museum, Duration, Signal, FieldValue, CityIndexEntry + sabitler; dict <-> dataclass
    schema.json    # JSON Schema (draft 2020-12)
    validation.py  # ValidationError, check_slug, validate_city_dict, parse_city
    synth.py       # Range, parse_duration, synthesize, confidence (saf)
    merge.py       # merge_city (spec Bölüm 6, saf)
    store.py       # Store protokolü, JsonStore, CityNotFound, atomik yazma
    table.py       # render_table (Türkçe tablo)
    cli.py         # get / stale / save / table
  tests/
    conftest.py          # rome_dict fixture
    test_models.py
    test_validation.py
    test_synth_parse.py
    test_synth.py
    test_merge.py
    test_store.py
    test_table.py
    test_cli.py
    test_skill_doc.py
  data/                  # ilk save'de oluşur; commit edilir (veritabanının kendisi)
```

---

### Task 1: Proje iskeleti ve veri modelleri

**Files:**
- Create: `.gitignore`, `pyproject.toml`, `museumdb/__init__.py`, `museumdb/models.py`
- Test: `tests/conftest.py`, `tests/test_models.py`

**Interfaces:**
- Consumes: —
- Produces (`museumdb.models`):
  - Sabitler: `SCHEMA_VERSION = 1`, `SOURCES: tuple[str, ...]`, `STRONG_SOURCES = ("google", "tripadvisor")`, `PLANNING_FIELDS = ("busiest", "queue_min", "advance_ticket")`, `VOLATILE_FIELDS = ("price", "hours")`
  - `Signal(source: str, value: str, checked: str, url: str | None = None)`; `Signal.from_dict(d) -> Signal`
  - `FieldValue(value: str | None, source: str | None, checked: str)`; `FieldValue.from_dict(d)`
  - `Duration(signals: list[Signal] = [], notes: list[str] = [], typical_min_h: float | None = None, typical_max_h: float | None = None, fast_h: float | None = None, thorough_h: float | None = None, confidence: str | None = None)`; `Duration.from_dict(d)`
  - `Museum(id: str, name: str, name_local=None, category=[], popularity_rank=None, address=None, coords: list[float] | None = None, website=None, user_notes=[], duration: Duration | None = None, planning: dict[str, FieldValue] = {}, volatile: dict[str, FieldValue] = {})`; `Museum.from_dict(d)`
  - `City(slug: str, name: str, queried_at: str, country: str | None = None, wikidata_id: str | None = None, museums: list[Museum] = [], schema_version: int = 1)`; `City.from_dict(d) -> City` (doğrulama YAPMAZ), `City.to_dict() -> dict` (spec dosya biçimi, `city.slug` dahil)
  - `CityIndexEntry(slug, name, country, wikidata_id, queried_at, museum_count: int)`
  - Test fixture `rome_dict` (`tests/conftest.py`): tam, geçerli, özet alanları sinyallerle tutarlı bir Roma belgesi (2 müze: `Q182955` Vatican Museums, `Q999001` Borghese Gallery). `Q999001` test için uydurma bir kimliktir.

- [ ] **Step 1: Proje dosyalarını oluştur**

`.gitignore`:
```
.venv/
__pycache__/
.pytest_cache/
*.egg-info/
```

`pyproject.toml`:
```toml
[build-system]
requires = ["setuptools>=68"]
build-backend = "setuptools.build_meta"

[project]
name = "museumdb"
version = "0.1.0"
description = "Museum visit-duration database for travelkardi"
requires-python = ">=3.11"
dependencies = ["jsonschema>=4.18"]

[project.optional-dependencies]
dev = ["pytest>=8"]

[tool.setuptools]
packages = ["museumdb"]

[tool.setuptools.package-data]
museumdb = ["schema.json"]

[tool.pytest.ini_options]
testpaths = ["tests"]
```

`museumdb/__init__.py`:
```python
"""Museum visit-duration database: models, validation, synthesis and storage."""
```

- [ ] **Step 2: Sanal ortamı kur**

Run:
```bash
cd /Users/hakan.suluoglu/Desktop/travelkardi
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
.venv/bin/python -c "import jsonschema, pytest; print('ok')"
```
Expected: son satır `ok`.

- [ ] **Step 3: Fixture ve başarısız testleri yaz**

`tests/conftest.py`:
```python
import copy

import pytest

# Summary fields are consistent with what synth.synthesize computes from the signals,
# so this dict survives a save/get round trip unchanged.
ROME = {
    "schema_version": 1,
    "city": {"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220", "queried_at": "2026-10-01"},
    "museums": [
        {
            "id": "Q182955",
            "name": "Vatican Museums",
            "name_local": "Musei Vaticani",
            "category": ["art", "history"],
            "popularity_rank": 1,
            "address": "Viale Vaticano, 00165 Roma",
            "coords": [41.9065, 12.4536],
            "website": "https://www.museivaticani.va",
            "user_notes": [],
            "duration": {
                "signals": [
                    {"source": "google", "value": "3–4 h", "checked": "2026-10-01", "url": None},
                    {"source": "tripadvisor", "value": "More than 3 hours", "checked": "2026-10-01", "url": None},
                    {"source": "reddit", "value": "~5 h with audio guide", "checked": "2026-10-01",
                     "url": "https://reddit.com/r/rome/x"},
                ],
                "notes": ["Sesli rehberle +1 saat"],
                "typical_min_h": 3, "typical_max_h": 4, "fast_h": 3, "thorough_h": 5, "confidence": "high",
            },
            "planning": {
                "busiest": {"value": "Sa–Ça 10:00–13:00", "source": "google", "checked": "2026-10-01"},
                "queue_min": {"value": "60–120", "source": "reddit", "checked": "2026-10-01"},
                "advance_ticket": {"value": "strongly_recommended", "source": "official", "checked": "2026-10-01"},
            },
            "volatile": {
                "price": {"value": "€20 adult", "source": "official", "checked": "2026-10-01"},
                "hours": {"value": "Mo–Sa 08:00–19:00", "source": "official", "checked": "2026-10-01"},
            },
        },
        {
            "id": "Q999001",
            "name": "Borghese Gallery",
            "name_local": "Galleria Borghese",
            "category": ["art"],
            "popularity_rank": 2,
            "address": None,
            "coords": None,
            "website": None,
            "user_notes": [],
            "duration": {
                "signals": [{"source": "tripadvisor", "value": "1-2 hours", "checked": "2026-10-01", "url": None}],
                "notes": [],
                "typical_min_h": 1, "typical_max_h": 2, "fast_h": 1, "thorough_h": 2, "confidence": "medium",
            },
            "planning": {},
            "volatile": {},
        },
    ],
}


@pytest.fixture
def rome_dict():
    return copy.deepcopy(ROME)
```

`tests/test_models.py`:
```python
from museumdb.models import City, Duration, FieldValue, Museum, Signal


def test_city_round_trips_through_dict(rome_dict):
    assert City.from_dict(rome_dict).to_dict() == rome_dict


def test_from_dict_builds_nested_types(rome_dict):
    city = City.from_dict(rome_dict)
    vatican = city.museums[0]
    assert city.slug == "rome"
    assert isinstance(vatican.duration, Duration)
    assert vatican.duration.signals[2] == Signal(
        "reddit", "~5 h with audio guide", "2026-10-01", "https://reddit.com/r/rome/x"
    )
    assert vatican.volatile["price"] == FieldValue("€20 adult", "official", "2026-10-01")
    assert city.museums[1].duration.signals[0].url is None


def test_minimal_museum_gets_defaults():
    m = Museum.from_dict({"id": "Q1", "name": "X"})
    assert m.duration is None
    assert m.planning == {} and m.volatile == {}
    assert m.user_notes == [] and m.category == []
    assert m.coords is None
```

- [ ] **Step 4: Testin başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'museumdb.models'`

- [ ] **Step 5: `museumdb/models.py` yaz**

```python
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
```

- [ ] **Step 6: Testlerin geçtiğini gör**

Run: `.venv/bin/python -m pytest tests/test_models.py -v`
Expected: 3 passed

- [ ] **Step 7: Commit**

```bash
git add .gitignore pyproject.toml museumdb/__init__.py museumdb/models.py tests/conftest.py tests/test_models.py
git commit -m "feat: museumdb package skeleton and data models" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 2: JSON Schema ve doğrulama

**Files:**
- Create: `museumdb/schema.json`, `museumdb/validation.py`
- Test: `tests/test_validation.py`

**Interfaces:**
- Consumes: `museumdb.models.City` (Task 1)
- Produces (`museumdb.validation`):
  - `class ValidationError(ValueError)`
  - `SLUG_RE` — `^[a-z0-9]+(?:-[a-z0-9]+)*$`
  - `check_slug(slug: str) -> None` — geçersizse `ValidationError("invalid slug ...")`
  - `validate_city_dict(data: dict) -> None` — şema + museum id tekrarı; hata mesajı `"<path>: <mesaj>; ..."` biçiminde, tekrar için `"duplicate museum ids: <id>, ..."`
  - `parse_city(data: dict) -> City` — doğrula, sonra `City.from_dict`

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_validation.py`:
```python
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
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_validation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'museumdb.validation'`

- [ ] **Step 3: `museumdb/schema.json` yaz**

```json
{
  "$schema": "https://json-schema.org/draft/2020-12/schema",
  "title": "travelkardi city museum durations",
  "type": "object",
  "required": ["schema_version", "city", "museums"],
  "additionalProperties": false,
  "properties": {
    "schema_version": {"const": 1},
    "city": {
      "type": "object",
      "required": ["slug", "name", "queried_at"],
      "additionalProperties": false,
      "properties": {
        "slug": {"$ref": "#/$defs/slug"},
        "name": {"type": "string", "minLength": 1},
        "country": {"type": ["string", "null"], "pattern": "^[A-Z]{2}$"},
        "wikidata_id": {"type": ["string", "null"], "pattern": "^Q[0-9]+$"},
        "queried_at": {"$ref": "#/$defs/date"}
      }
    },
    "museums": {"type": "array", "items": {"$ref": "#/$defs/museum"}}
  },
  "$defs": {
    "slug": {"type": "string", "pattern": "^[a-z0-9]+(-[a-z0-9]+)*$"},
    "date": {"type": "string", "pattern": "^[0-9]{4}-[0-9]{2}-[0-9]{2}$", "format": "date"},
    "source": {"enum": ["google", "tripadvisor", "reddit", "blog", "official", "wikidata", "osm"]},
    "hours": {"type": ["number", "null"], "minimum": 0},
    "field_value": {
      "type": "object",
      "required": ["value", "source", "checked"],
      "additionalProperties": false,
      "properties": {
        "value": {"type": ["string", "null"]},
        "source": {"anyOf": [{"$ref": "#/$defs/source"}, {"type": "null"}]},
        "checked": {"$ref": "#/$defs/date"}
      }
    },
    "signal": {
      "type": "object",
      "required": ["source", "value", "checked"],
      "additionalProperties": false,
      "properties": {
        "source": {"$ref": "#/$defs/source"},
        "value": {"type": "string", "minLength": 1},
        "url": {"type": ["string", "null"]},
        "checked": {"$ref": "#/$defs/date"}
      }
    },
    "duration": {
      "type": "object",
      "required": ["signals"],
      "additionalProperties": false,
      "properties": {
        "signals": {"type": "array", "items": {"$ref": "#/$defs/signal"}},
        "notes": {"type": "array", "items": {"type": "string"}},
        "typical_min_h": {"$ref": "#/$defs/hours"},
        "typical_max_h": {"$ref": "#/$defs/hours"},
        "fast_h": {"$ref": "#/$defs/hours"},
        "thorough_h": {"$ref": "#/$defs/hours"},
        "confidence": {"enum": ["high", "medium", "low", null]}
      }
    },
    "museum": {
      "type": "object",
      "required": ["id", "name"],
      "additionalProperties": false,
      "properties": {
        "id": {
          "type": "string",
          "pattern": "^(Q[0-9]+|osm:(node|way|relation)/[0-9]+|slug:[a-z0-9]+(-[a-z0-9]+)*/[a-z0-9]+(-[a-z0-9]+)*)$"
        },
        "name": {"type": "string", "minLength": 1},
        "name_local": {"type": ["string", "null"]},
        "category": {"type": "array", "items": {"type": "string"}},
        "popularity_rank": {"type": ["integer", "null"], "minimum": 1},
        "address": {"type": ["string", "null"]},
        "coords": {
          "oneOf": [
            {"type": "null"},
            {
              "type": "array",
              "minItems": 2,
              "maxItems": 2,
              "prefixItems": [
                {"type": "number", "minimum": -90, "maximum": 90},
                {"type": "number", "minimum": -180, "maximum": 180}
              ]
            }
          ]
        },
        "website": {"type": ["string", "null"]},
        "user_notes": {"type": "array", "items": {"type": "string"}},
        "duration": {"anyOf": [{"type": "null"}, {"$ref": "#/$defs/duration"}]},
        "planning": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "busiest": {"$ref": "#/$defs/field_value"},
            "queue_min": {"$ref": "#/$defs/field_value"},
            "advance_ticket": {
              "allOf": [
                {"$ref": "#/$defs/field_value"},
                {"properties": {"value": {"enum": ["required", "strongly_recommended", "recommended", "not_needed", null]}}}
              ]
            }
          }
        },
        "volatile": {
          "type": "object",
          "additionalProperties": false,
          "properties": {
            "price": {"$ref": "#/$defs/field_value"},
            "hours": {"$ref": "#/$defs/field_value"}
          }
        }
      }
    }
  }
}
```

- [ ] **Step 4: `museumdb/validation.py` yaz**

```python
"""Schema validation and slug checks for city documents."""
from __future__ import annotations

import json
import re
from functools import cache
from importlib.resources import files

from jsonschema import Draft202012Validator

from museumdb.models import City

SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
MAX_REPORTED_ERRORS = 10


class ValidationError(ValueError):
    """A city document or slug failed validation."""


@cache
def _validator() -> Draft202012Validator:
    schema = json.loads(files("museumdb").joinpath("schema.json").read_text(encoding="utf-8"))
    return Draft202012Validator(schema, format_checker=Draft202012Validator.FORMAT_CHECKER)


def check_slug(slug: str) -> None:
    if not isinstance(slug, str) or not SLUG_RE.fullmatch(slug):
        raise ValidationError(
            f"invalid slug {slug!r}: use lowercase English letters, digits and single hyphens (e.g. 'new-york')"
        )


def validate_city_dict(data: dict) -> None:
    errors = sorted(_validator().iter_errors(data), key=lambda e: str(list(e.absolute_path)))
    if errors:
        messages = [
            f"{'/'.join(map(str, e.absolute_path)) or '<root>'}: {e.message}"
            for e in errors[:MAX_REPORTED_ERRORS]
        ]
        raise ValidationError("; ".join(messages))
    ids = [m["id"] for m in data["museums"]]
    duplicates = sorted({i for i in ids if ids.count(i) > 1})
    if duplicates:
        raise ValidationError(f"duplicate museum ids: {', '.join(duplicates)}")


def parse_city(data: dict) -> City:
    validate_city_dict(data)
    return City.from_dict(data)
```

- [ ] **Step 5: Testlerin geçtiğini gör**

Run: `.venv/bin/python -m pytest tests/test_validation.py -v`
Expected: tümü PASS. (`2026-13-45` testi format denetimine dayanır; FAIL olursa `format_checker` parametresinin verildiğini kontrol et.)

- [ ] **Step 6: Commit**

```bash
git add museumdb/schema.json museumdb/validation.py tests/test_validation.py
git commit -m "feat: JSON schema and city document validation" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 3: Süre metni ayrıştırma (`parse_duration`)

**Files:**
- Create: `museumdb/synth.py`
- Test: `tests/test_synth_parse.py`

**Interfaces:**
- Consumes: —
- Produces (`museumdb.synth`):
  - `@dataclass(frozen=True) Range(lo: float, hi: float | None)` — `hi=None` açık uçlu ("More than 3 hours"); `Range.overlaps(other: Range) -> bool` (uçlar dahil)
  - `parse_duration(text: str) -> Range | None` — saat cinsinden, 2 ondalığa yuvarlı; anlaşılmazsa `None`
  - `MAX_HOURS = 12.0` — bu değerden büyük her sayı metni geçersiz kılar

Ayrıştırma kuralları: ilk iki sayı kullanılır (iki sayı → sıralı aralık); en az bir birim (h/hr/hour/saat/sa, min/minute/dk/dakika) şart; birimsiz sayı, sonraki birimli sayının (yoksa öncekinin) birimini alır; tek sayıda "more than / over / at least / N+" → açık uç, "less than / under / up to / <" → `(x/2, x)`, aksi halde `(x, x)`.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_synth_parse.py`:
```python
import pytest

from museumdb.synth import Range, parse_duration


@pytest.mark.parametrize(
    "text, expected",
    [
        ("3–4 h", Range(3, 4)),
        ("More than 3 hours", Range(3, None)),
        ("1-2 hours", Range(1, 2)),
        ("~5 h", Range(5, 5)),
        ("~5 h with audio guide", Range(5, 5)),
        ("90 min", Range(1.5, 1.5)),
        ("<1 hour", Range(0.5, 1)),
        ("Less than 1 hour", Range(0.5, 1)),
        ("3+ hours", Range(3, None)),
        ("2 to 3 hrs", Range(2, 3)),
        ("about 2 hours", Range(2, 2)),
        ("30 min - 1 hour", Range(0.5, 1)),
        ("4-2 hours", Range(2, 4)),
        ("1,5 saat", Range(1.5, 1.5)),
        ("2-3 saat", Range(2, 3)),
        ("45 dk", Range(0.75, 0.75)),
        ("People typically spend 1.5 hours here", Range(1.5, 1.5)),
    ],
)
def test_parses_known_formats(text, expected):
    assert parse_duration(text) == expected


@pytest.mark.parametrize(
    "text",
    [
        "",
        "half a day",
        "3 people",          # numbers but no time unit
        "Mo–Sa 08:00–19:00",  # opening hours, not a duration
        "15 hours",          # beyond MAX_HOURS: not a museum visit
        "2h30",              # must never become a 2–30 h range
        "0 h",
    ],
)
def test_returns_none_for_unusable_text(text):
    assert parse_duration(text) is None


def test_overlap_includes_touching_and_open_ranges():
    assert Range(3, 4).overlaps(Range(3, None))
    assert Range(2, 3).overlaps(Range(3, 4))
    assert not Range(1, 2).overlaps(Range(3, None))
    assert not Range(5, 5).overlaps(Range(3, 4))
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_synth_parse.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'museumdb.synth'`

- [ ] **Step 3: `museumdb/synth.py` yaz (yalnızca ayrıştırma kısmı)**

```python
"""Turn raw duration signals into a summary range and confidence level (pure functions)."""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

MAX_HOURS = 12.0
_MINUTE_UNITS = {"min", "mins", "minute", "minutes", "dk", "dakika"}
# A number, optionally followed by a time unit; the unit must not run into further letters.
_TOKEN = re.compile(r"(\d+(?:[.,]\d+)?)\s*(hours?|hrs?|h|saat|sa|minutes?|mins?|dakika|dk)?(?![^\W\d_])")
_OPEN = re.compile(r"more than|\bover\b|at least|\d\s*\+")
_AT_MOST = re.compile(r"less than|\bunder\b|up to|<")
_PLUS = re.compile(r"(\d)\s*\+")


@dataclass(frozen=True)
class Range:
    lo: float
    hi: float | None  # None = open-ended, e.g. "More than 3 hours"

    def overlaps(self, other: Range) -> bool:
        self_hi = math.inf if self.hi is None else self.hi
        other_hi = math.inf if other.hi is None else other.hi
        return self.lo <= other_hi and other.lo <= self_hi


def parse_duration(text: str) -> Range | None:
    """Parse "3–4 h", "More than 3 hours", "90 min", ... into hours; None if not understood."""
    t = text.lower()
    open_ended = bool(_OPEN.search(t))
    at_most = bool(_AT_MOST.search(t))
    t = _PLUS.sub(r"\1 ", t)
    tokens = [(float(num.replace(",", ".")), unit) for num, unit in _TOKEN.findall(t)]
    if not any(unit for _, unit in tokens):
        return None
    hours = [
        round(_to_hours(num, unit or _nearest_unit(tokens, i)), 2)
        for i, (num, unit) in enumerate(tokens[:2])
    ]
    if any(h <= 0 or h > MAX_HOURS for h in hours):
        return None
    if len(hours) == 2:
        lo, hi = sorted(hours)
        return Range(lo, hi)
    (x,) = hours
    if open_ended:
        return Range(x, None)
    if at_most:
        return Range(round(x / 2, 2), x)
    return Range(x, x)


def _nearest_unit(tokens: list[tuple[float, str]], i: int) -> str:
    """Unit for a bare number: the next explicit unit, else the previous one ("1-2 hours")."""
    for _, unit in tokens[i + 1:]:
        if unit:
            return unit
    for _, unit in reversed(tokens[:i]):
        if unit:
            return unit
    return "h"


def _to_hours(num: float, unit: str) -> float:
    return num / 60 if unit in _MINUTE_UNITS else num
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/bin/python -m pytest tests/test_synth_parse.py -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add museumdb/synth.py tests/test_synth_parse.py
git commit -m "feat: parse free-text visit durations into hour ranges" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 4: Özet ve güven hesaplama (`synthesize`)

**Files:**
- Modify: `museumdb/synth.py` (dosya sonuna ekle; import satırını güncelle)
- Test: `tests/test_synth.py`

**Interfaces:**
- Consumes: `Range`, `parse_duration` (Task 3); `Duration`, `Signal`, `STRONG_SOURCES` (Task 1)
- Produces (`museumdb.synth`):
  - `synthesize(signals: list[Signal], notes: list[str] | None = None) -> Duration | None` — sinyal yoksa `None`; aksi halde sinyalleri ve notları taşıyan, özet alanları hesaplanmış yeni `Duration`
  - `confidence(parsed: list[tuple[str, Range]]) -> str | None` — `(source, range)` çiftlerinden `"high" | "medium" | "low"`, boş listede `None`

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_synth.py`:
```python
from museumdb.models import Signal
from museumdb.synth import Range, confidence, synthesize


def sig(source, value):
    return Signal(source, value, "2026-10-01")


def summary(d):
    return (d.typical_min_h, d.typical_max_h, d.fast_h, d.thorough_h, d.confidence)


def test_no_signals_gives_none():
    assert synthesize([]) is None


def test_overlapping_strong_sources_are_high():
    d = synthesize([sig("google", "3–4 h"), sig("tripadvisor", "More than 3 hours"),
                    sig("reddit", "~5 h with audio guide")])
    assert summary(d) == (3, 4, 3, 5, "high")


def test_single_strong_source_is_medium():
    assert summary(synthesize([sig("tripadvisor", "1-2 hours")])) == (1, 2, 1, 2, "medium")


def test_non_overlapping_strong_sources_are_medium_with_hull_range():
    d = synthesize([sig("google", "1-2 h"), sig("tripadvisor", "3-4 hours")])
    assert summary(d) == (1, 4, 1, 4, "medium")


def test_hull_with_open_range_stays_open():
    d = synthesize([sig("google", "1-2 h"), sig("tripadvisor", "More than 3 hours")])
    assert summary(d) == (1, None, 1, 3, "medium")


def test_strong_and_weak_overlap_is_high_but_typical_uses_strong_only():
    d = synthesize([sig("tripadvisor", "2-3 hours"), sig("reddit", "3 hours")])
    assert summary(d) == (2, 3, 2, 3, "high")


def test_only_weak_sources_are_low_even_when_overlapping():
    d = synthesize([sig("reddit", "2-3 hours"), sig("blog", "about 2 hours")])
    assert summary(d) == (2, 2, 2, 3, "low")


def test_same_source_twice_is_not_high():
    d = synthesize([sig("google", "2-3 h"), sig("google", "2 h")])
    assert d.confidence == "medium"


def test_unparseable_signals_are_kept_but_not_summarised():
    signals = [sig("blog", "half a day"), sig("reddit", "2h30")]
    d = synthesize(signals)
    assert d.signals == signals
    assert summary(d) == (None, None, None, None, None)


def test_unparseable_signal_is_ignored_next_to_parseable_one():
    d = synthesize([sig("google", "3-4 h"), sig("blog", "half a day")])
    assert summary(d) == (3, 4, 3, 4, "medium")
    assert len(d.signals) == 2


def test_notes_are_carried_over():
    assert synthesize([sig("google", "1 h")], ["Sesli rehberle +1 saat"]).notes == ["Sesli rehberle +1 saat"]


def test_confidence_of_nothing_is_none():
    assert confidence([]) is None
    assert confidence([("osm", Range(1, 2))]) == "low"
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_synth.py -v`
Expected: FAIL — `ImportError: cannot import name 'confidence' from 'museumdb.synth'`

- [ ] **Step 3: `museumdb/synth.py`'ye ekle**

Import bloğuna (`from dataclasses import dataclass` satırından sonra) ekle:
```python

from museumdb.models import STRONG_SOURCES, Duration, Signal
```

Dosya sonuna ekle:
```python


def synthesize(signals: list[Signal], notes: list[str] | None = None) -> Duration | None:
    """Rebuild the duration summary from raw signals; None when there are no signals."""
    if not signals:
        return None
    duration = Duration(signals=list(signals), notes=list(notes or []))
    parsed = [(s.source, r) for s in signals if (r := parse_duration(s.value)) is not None]
    if not parsed:
        return duration
    ranges = [r for _, r in parsed]
    strong = [r for source, r in parsed if source in STRONG_SOURCES]
    duration.typical_min_h, duration.typical_max_h = _typical(strong or ranges)
    duration.fast_h = min(r.lo for r in ranges)
    duration.thorough_h = max(r.lo if r.hi is None else r.hi for r in ranges)
    duration.confidence = confidence(parsed)
    return duration


def _typical(ranges: list[Range]) -> tuple[float, float | None]:
    """Common intersection of the ranges, or their hull when they do not all overlap."""
    lo = max(r.lo for r in ranges)
    closed = [r.hi for r in ranges if r.hi is not None]
    hi = min(closed) if closed else None
    if hi is None or lo <= hi:
        return lo, hi
    hull_hi = max(closed) if len(closed) == len(ranges) else None
    return min(r.lo for r in ranges), hull_hi


def confidence(parsed: list[tuple[str, Range]]) -> str | None:
    """high: two different sources overlap (one of them strong); medium: any strong; low: weak only."""
    if not parsed:
        return None
    for i, (source_a, a) in enumerate(parsed):
        for source_b, b in parsed[i + 1:]:
            involves_strong = source_a in STRONG_SOURCES or source_b in STRONG_SOURCES
            if source_a != source_b and involves_strong and a.overlaps(b):
                return "high"
    if any(source in STRONG_SOURCES for source, _ in parsed):
        return "medium"
    return "low"
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/bin/python -m pytest tests/test_synth.py tests/test_synth_parse.py -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add museumdb/synth.py tests/test_synth.py
git commit -m "feat: synthesize duration summary and confidence from signals" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 5: Birleştirme kuralları (`merge_city`)

**Files:**
- Create: `museumdb/merge.py`
- Test: `tests/test_merge.py`

**Interfaces:**
- Consumes: `City`, `Museum`, `Duration`, `FieldValue` (Task 1); `synthesize` (Task 4)
- Produces (`museumdb.merge`):
  - `merge_city(existing: City | None, incoming: City) -> City` — yeni nesne döner, girdileri değiştirmez; tüm `duration` özetlerini `synthesize` ile yeniden hesaplar; müzeleri `(popularity_rank yoksa sona, rank, name)` ile sıralar.

Kurallar (spec Bölüm 6 + sapma 6): müzeler `id` ile eşlenir; gelen `null` skaler alan mevcut değeri ezmez; boş `category` ezmez; gelen `FieldValue.value` `null` ve mevcut dolu ise yalnızca `checked` güncellenir; gelen kaynaklar o kaynağın eski sinyallerinin hepsini değiştirir; boş `notes` ezmez; gelen `duration: null` ezmez; `user_notes` mevcut müzede asla değişmez; gelende olmayan mevcut müzeler korunur.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_merge.py`:
```python
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
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_merge.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'museumdb.merge'`

- [ ] **Step 3: `museumdb/merge.py` yaz**

```python
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
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/bin/python -m pytest tests/test_merge.py -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add museumdb/merge.py tests/test_merge.py
git commit -m "feat: merge incoming city drafts into stored records" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 6: Depolama (`Store` protokolü + `JsonStore`)

**Files:**
- Create: `museumdb/store.py`
- Test: `tests/test_store.py`

**Interfaces:**
- Consumes: `City`, `CityIndexEntry`, `PLANNING_FIELDS`, `VOLATILE_FIELDS` (Task 1); `ValidationError`, `check_slug`, `parse_city`, `validate_city_dict` (Task 2); `merge_city` (Task 5)
- Produces (`museumdb.store`):
  - `DEFAULT_MAX_AGE_DAYS = 90`
  - `class CityNotFound(LookupError)`
  - `class Store(Protocol)`: `get_city(slug) -> City | None`, `save_city(city: City) -> None`, `stale_fields(slug, max_age_days=90) -> list[tuple[str, str]]`, `list_cities() -> list[CityIndexEntry]`
  - `JsonStore(root: Path | str, today: Callable[[], date] = date.today)` — `Store`'u uygular. `get_city` bozuk/geçersiz dosyada `ValidationError`; geçersiz slug'da `ValidationError`. `stale_fields` bilinmeyen şehirde `CityNotFound`; çıktı müze sırası, sonra `planning.busiest, planning.queue_min, planning.advance_ticket, volatile.price, volatile.hours` sırası; yaş `> max_age_days` ise bayat; anahtar hiç yoksa bayat.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_store.py`:
```python
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
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'museumdb.store'`

- [ ] **Step 3: `museumdb/store.py` yaz**

```python
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
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/bin/python -m pytest tests/test_store.py -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add museumdb/store.py tests/test_store.py
git commit -m "feat: JsonStore with atomic writes, index and staleness" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 7: Tablo çıktısı (`render_table`)

**Files:**
- Create: `museumdb/table.py`
- Test: `tests/test_table.py`

**Interfaces:**
- Consumes: `City`, `Museum` (Task 1)
- Produces (`museumdb.table`):
  - `render_table(city: City) -> str` — ilk satır `"<Şehir> — N müze (H yüksek, M orta, L düşük güven[, X veri yok])"`; sonra başlık satırı `Müze  Süre  Hızlı/Detaylı  Not` ve müze başına bir satır; ilk üç sütun hizalı, satır sonu boşluksuz.
  - Süre: `"3–4 sa"`, tek değer `"2 sa"`, açık uç `"3+ sa"`, ondalık virgülle `"1,5–2,5 sa"`, özet yoksa `"veri yok"`. Hızlı/Detaylı: `"3 / 5 sa"` ya da `"—"`. Not: `advance_ticket` değeri `required`/`strongly_recommended`/`recommended` ise Türkçe karşılığı, yoksa ilk süre notu, yoksa boş.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_table.py`:
```python
import pytest

from museumdb.models import City
from museumdb.table import render_table


def lines_of(d):
    return render_table(City.from_dict(d)).splitlines()


def test_header_counts_confidence(rome_dict):
    assert lines_of(rome_dict)[0] == "Rome — 2 müze (1 yüksek, 1 orta, 0 düşük güven)"


def test_rows_show_duration_range_and_note(rome_dict):
    _, head, vatican, borghese = lines_of(rome_dict)
    assert head.split()[0] == "Müze"
    assert vatican.startswith("Vatican Museums")
    assert "3–4 sa" in vatican and "3 / 5 sa" in vatican
    assert vatican.endswith("Bilet önceden şiddetle önerilir")
    assert borghese.startswith("Borghese Gallery")
    assert "1–2 sa" in borghese and "1 / 2 sa" in borghese
    assert borghese == borghese.rstrip()


def test_columns_are_aligned(rome_dict):
    _, head, vatican, borghese = lines_of(rome_dict)
    assert head.index("Süre") == vatican.index("3–4 sa") == borghese.index("1–2 sa")
    assert head.index("Hızlı/Detaylı") == vatican.index("3 / 5 sa") == borghese.index("1 / 2 sa")


def test_missing_duration_shows_veri_yok(rome_dict):
    rome_dict["museums"][1]["duration"] = None
    lines = lines_of(rome_dict)
    assert lines[0] == "Rome — 2 müze (1 yüksek, 0 orta, 0 düşük güven, 1 veri yok)"
    assert "veri yok" in lines[3] and "—" in lines[3]


def test_unparsed_signals_count_as_veri_yok(rome_dict):
    rome_dict["museums"][1]["duration"] = {
        "signals": [{"source": "blog", "value": "half a day", "checked": "2026-10-01", "url": None}],
        "notes": [], "typical_min_h": None, "typical_max_h": None,
        "fast_h": None, "thorough_h": None, "confidence": None,
    }
    lines = lines_of(rome_dict)
    assert lines[0].endswith(", 1 veri yok)")
    assert "veri yok" in lines[3]


@pytest.mark.parametrize("lo, hi, text", [(3, None, "3+ sa"), (2, 2, "2 sa"), (1.5, 2.5, "1,5–2,5 sa")])
def test_duration_text_formats(rome_dict, lo, hi, text):
    d = rome_dict["museums"][0]["duration"]
    d["typical_min_h"], d["typical_max_h"] = lo, hi
    assert text in lines_of(rome_dict)[2]


def test_note_falls_back_to_first_duration_note(rome_dict):
    rome_dict["museums"][0]["planning"].pop("advance_ticket")
    assert lines_of(rome_dict)[2].endswith("Sesli rehberle +1 saat")
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_table.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'museumdb.table'`

- [ ] **Step 3: `museumdb/table.py` yaz**

```python
"""Plain-text summary table of a city's museums (Turkish labels)."""
from __future__ import annotations

from museumdb.models import City, Museum

NO_DATA = "veri yok"
CONFIDENCE_LABELS = (("high", "yüksek"), ("medium", "orta"), ("low", "düşük"))
TICKET_NOTES = {
    "required": "Bilet önceden şart",
    "strongly_recommended": "Bilet önceden şiddetle önerilir",
    "recommended": "Bilet önceden önerilir",
}
HEADER = ("Müze", "Süre", "Hızlı/Detaylı", "Not")


def render_table(city: City) -> str:
    rows = [HEADER] + [(m.name, _duration_text(m), _range_text(m), _note_text(m)) for m in city.museums]
    widths = [max(len(row[i]) for row in rows) for i in range(3)]
    lines = [_summary_line(city)]
    for row in rows:
        aligned = "  ".join(cell.ljust(width) for cell, width in zip(row[:3], widths))
        lines.append(f"{aligned}  {row[3]}".rstrip())
    return "\n".join(lines)


def _summary_line(city: City) -> str:
    counts = {level: 0 for level, _ in CONFIDENCE_LABELS}
    no_data = 0
    for m in city.museums:
        level = m.duration.confidence if m.duration else None
        if level in counts:
            counts[level] += 1
        else:
            no_data += 1
    summary = ", ".join(f"{counts[level]} {label}" for level, label in CONFIDENCE_LABELS) + " güven"
    if no_data:
        summary += f", {no_data} {NO_DATA}"
    return f"{city.name} — {len(city.museums)} müze ({summary})"


def _hours(x: float) -> str:
    return f"{x:g}".replace(".", ",")


def _duration_text(m: Museum) -> str:
    d = m.duration
    if d is None or d.typical_min_h is None:
        return NO_DATA
    if d.typical_max_h is None:
        return f"{_hours(d.typical_min_h)}+ sa"
    if d.typical_min_h == d.typical_max_h:
        return f"{_hours(d.typical_min_h)} sa"
    return f"{_hours(d.typical_min_h)}–{_hours(d.typical_max_h)} sa"


def _range_text(m: Museum) -> str:
    d = m.duration
    if d is None or d.fast_h is None:
        return "—"
    return f"{_hours(d.fast_h)} / {_hours(d.thorough_h)} sa"


def _note_text(m: Museum) -> str:
    ticket = m.planning.get("advance_ticket")
    if ticket is not None and ticket.value in TICKET_NOTES:
        return TICKET_NOTES[ticket.value]
    if m.duration is not None and m.duration.notes:
        return m.duration.notes[0]
    return ""
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/bin/python -m pytest tests/test_table.py -v`
Expected: tümü PASS

- [ ] **Step 5: Commit**

```bash
git add museumdb/table.py tests/test_table.py
git commit -m "feat: Turkish summary table for a city's museums" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 8: CLI (`get` / `stale` / `save` / `table`)

**Files:**
- Create: `museumdb/cli.py`
- Test: `tests/test_cli.py`

**Interfaces:**
- Consumes: `JsonStore`, `CityNotFound` (Task 6); `render_table` (Task 7); `ValidationError`, `check_slug`, `parse_city` (Task 2)
- Produces:
  - `museumdb.cli.main(argv: list[str] | None = None) -> int`
  - Komut satırı: `python -m museumdb.cli [--root DIR] <get|stale|save|table> <slug>`; `stale` ayrıca `--max-age-days N` (varsayılan 90). `--root` varsayılanı `$MUSEUMDB_ROOT`, o da yoksa `./data`.
  - Çıkış kodları: `0` başarılı, `1` şehir kaydı yok, `2` geçersiz slug / geçersiz JSON / şema hatası / slug uyuşmazlığı / bozuk kayıt. Hatalar stderr'e `error: ...` olarak yazılır.
  - `get` → şehir JSON'u (UTF-8, girintili). `stale` → `[{"museum_id": ..., "field": "volatile.price"}, ...]`. `save` → stdin'den taslak; `city.slug` yoksa argümandan doldurur, farklıysa reddeder; başarıda `saved <slug>: N museums`. `table` → `render_table` çıktısı.

- [ ] **Step 1: Başarısız testleri yaz**

`tests/test_cli.py`:
```python
import io
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from museumdb.cli import main

REPO = Path(__file__).resolve().parents[1]
FIELDS = ("planning.busiest", "planning.queue_min", "planning.advance_ticket", "volatile.price", "volatile.hours")


@pytest.fixture
def run(tmp_path, monkeypatch, capsys):
    def _run(*argv, stdin=""):
        monkeypatch.setattr(sys, "stdin", io.StringIO(stdin))
        code = main(["--root", str(tmp_path), *argv])
        out, err = capsys.readouterr()
        return code, out, err

    return _run


def test_get_unknown_city_exits_1(run):
    code, out, err = run("get", "rome")
    assert code == 1 and out == "" and "rome" in err


def test_save_then_get(run, rome_dict):
    code, out, _ = run("save", "rome", stdin=json.dumps(rome_dict))
    assert code == 0 and out.strip() == "saved rome: 2 museums"
    code, out, _ = run("get", "rome")
    assert code == 0 and json.loads(out) == rome_dict


def test_save_fills_missing_slug(run, rome_dict):
    del rome_dict["city"]["slug"]
    assert run("save", "rome", stdin=json.dumps(rome_dict))[0] == 0
    assert json.loads(run("get", "rome")[1])["city"]["slug"] == "rome"


def test_save_rejects_slug_mismatch(run, rome_dict, tmp_path):
    code, _, err = run("save", "paris", stdin=json.dumps(rome_dict))
    assert code == 2 and "does not match" in err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("stdin", ["", "{oops", "[]", '{"city": "rome"}'])
def test_save_rejects_malformed_input(run, tmp_path, stdin):
    code, _, err = run("save", "rome", stdin=stdin)
    assert code == 2 and err.startswith("error:")
    assert list(tmp_path.iterdir()) == []


def test_save_rejects_schema_violation(run, rome_dict, tmp_path):
    rome_dict["museums"][0]["duration"]["signals"][0]["source"] = "yelp"
    code, _, err = run("save", "rome", stdin=json.dumps(rome_dict))
    assert code == 2 and "yelp" in err
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("command", ["get", "stale", "save", "table"])
def test_bad_slug_exits_2(run, tmp_path, command):
    code, _, err = run(command, "../etc")
    assert code == 2 and "invalid slug" in err
    assert list(tmp_path.iterdir()) == []


def test_stale_lists_never_checked_fields(run, rome_dict):
    run("save", "rome", stdin=json.dumps(rome_dict))
    code, out, _ = run("stale", "rome", "--max-age-days", "100000")
    assert code == 0
    assert json.loads(out) == [{"museum_id": "Q999001", "field": f} for f in FIELDS]


def test_stale_unknown_city_exits_1(run):
    assert run("stale", "rome")[0] == 1


def test_table(run, rome_dict):
    run("save", "rome", stdin=json.dumps(rome_dict))
    code, out, _ = run("table", "rome")
    assert code == 0
    assert out.splitlines()[0] == "Rome — 2 müze (1 yüksek, 1 orta, 0 düşük güven)"


def test_table_unknown_city_exits_1(run):
    assert run("table", "rome")[0] == 1


def test_corrupt_record_exits_2(run, tmp_path):
    (tmp_path / "cities").mkdir()
    (tmp_path / "cities" / "rome.json").write_text("{not json", encoding="utf-8")
    code, _, err = run("get", "rome")
    assert code == 2 and "invalid JSON" in err


def test_module_entry_point(tmp_path, rome_dict):
    env = {**os.environ, "PYTHONUTF8": "1"}
    base = [sys.executable, "-m", "museumdb.cli", "--root", str(tmp_path)]
    saved = subprocess.run([*base, "save", "rome"], input=json.dumps(rome_dict), capture_output=True,
                           text=True, encoding="utf-8", cwd=REPO, env=env)
    assert saved.returncode == 0, saved.stderr
    table = subprocess.run([*base, "table", "rome"], capture_output=True, text=True, encoding="utf-8",
                           cwd=REPO, env=env)
    assert table.returncode == 0 and "Vatican Museums" in table.stdout
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'museumdb.cli'`

- [ ] **Step 3: `museumdb/cli.py` yaz**

```python
"""Command line for the museum DB.

    python -m museumdb.cli get <slug>           # stored JSON; exit 1 if unknown
    python -m museumdb.cli stale <slug>         # stale fields as JSON
    python -m museumdb.cli save <slug> < draft.json
    python -m museumdb.cli table <slug>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

from museumdb.store import DEFAULT_MAX_AGE_DAYS, CityNotFound, JsonStore
from museumdb.table import render_table
from museumdb.validation import ValidationError, check_slug, parse_city

EXIT_OK = 0
EXIT_NOT_FOUND = 1
EXIT_INVALID = 2


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    store = JsonStore(args.root)
    try:
        check_slug(args.slug)
        return _COMMANDS[args.command](store, args)
    except ValidationError as e:
        print(f"error: {e}", file=sys.stderr)
        return EXIT_INVALID


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="museumdb")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(os.environ.get("MUSEUMDB_ROOT", "data")),
        help="data directory (default: $MUSEUMDB_ROOT or ./data)",
    )
    sub = parser.add_subparsers(dest="command", required=True)
    for name, help_text in (
        ("get", "print the stored city JSON"),
        ("stale", "list planning/volatile fields that need refreshing"),
        ("save", "validate, merge and store a draft read from stdin"),
        ("table", "print a summary table"),
    ):
        command = sub.add_parser(name, help=help_text)
        command.add_argument("slug")
        if name == "stale":
            command.add_argument("--max-age-days", type=int, default=DEFAULT_MAX_AGE_DAYS)
    return parser


def _get(store: JsonStore, args: argparse.Namespace) -> int:
    city = store.get_city(args.slug)
    if city is None:
        return _not_found(args.slug)
    _print_json(city.to_dict())
    return EXIT_OK


def _stale(store: JsonStore, args: argparse.Namespace) -> int:
    try:
        fields = store.stale_fields(args.slug, args.max_age_days)
    except CityNotFound:
        return _not_found(args.slug)
    _print_json([{"museum_id": museum_id, "field": field} for museum_id, field in fields])
    return EXIT_OK


def _save(store: JsonStore, args: argparse.Namespace) -> int:
    try:
        data = json.load(sys.stdin)
    except json.JSONDecodeError as e:
        raise ValidationError(f"draft is not valid JSON: {e}") from e
    if not isinstance(data, dict) or not isinstance(data.get("city"), dict):
        raise ValidationError("draft must be a JSON object with a 'city' object")
    draft_slug = data["city"].setdefault("slug", args.slug)
    if draft_slug != args.slug:
        raise ValidationError(f"draft slug {draft_slug!r} does not match {args.slug!r}")
    store.save_city(parse_city(data))
    saved = store.get_city(args.slug)
    print(f"saved {args.slug}: {len(saved.museums)} museums")
    return EXIT_OK


def _table(store: JsonStore, args: argparse.Namespace) -> int:
    city = store.get_city(args.slug)
    if city is None:
        return _not_found(args.slug)
    print(render_table(city))
    return EXIT_OK


def _not_found(slug: str) -> int:
    print(f"error: no record for {slug!r}", file=sys.stderr)
    return EXIT_NOT_FOUND


def _print_json(data: object) -> None:
    print(json.dumps(data, ensure_ascii=False, indent=2))


_COMMANDS = {"get": _get, "stale": _stale, "save": _save, "table": _table}

if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/bin/python -m pytest tests/test_cli.py -v`
Expected: tümü PASS

- [ ] **Step 5: Tüm test paketini çalıştır**

Run: `.venv/bin/python -m pytest -q`
Expected: tümü PASS, hata yok

- [ ] **Step 6: Commit**

```bash
git add museumdb/cli.py tests/test_cli.py
git commit -m "feat: museumdb CLI with get/stale/save/table" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 9: `/muze` skill'i

**Files:**
- Create: `.claude/skills/muze/SKILL.md`
- Test: `tests/test_skill_doc.py`

**Interfaces:**
- Consumes: CLI sözleşmesi (Task 8): `.venv/bin/python -m museumdb.cli <get|stale|save|table> <slug>`, çıkış kodları 0/1/2, `stale` JSON biçimi; şema (Task 2).
- Produces: `/muze <şehir> [--yenile]` komutu. Skill'deki `## Taslak örneği` başlığı altındaki ilk ```` ```json ```` bloğu şemaya uygun olmak zorunda (test bunu denetler).

- [ ] **Step 1: Başarısız testi yaz**

`tests/test_skill_doc.py`:
```python
import json
import re
from pathlib import Path

from museumdb.validation import parse_city

SKILL = Path(__file__).resolve().parents[1] / ".claude" / "skills" / "muze" / "SKILL.md"


def test_skill_frontmatter_names_the_command():
    assert SKILL.read_text(encoding="utf-8").startswith("---\nname: muze\n")


def test_skill_draft_example_is_a_valid_document():
    text = SKILL.read_text(encoding="utf-8")
    match = re.search(r"## Taslak örneği.*?```json\n(.*?)```", text, re.S)
    assert match, "SKILL.md needs a ```json block under '## Taslak örneği'"
    city = parse_city(json.loads(match.group(1)))
    assert city.museums, "example should contain at least one museum"
```

- [ ] **Step 2: Testin başarısız olduğunu gör**

Run: `.venv/bin/python -m pytest tests/test_skill_doc.py -v`
Expected: FAIL — `FileNotFoundError` (SKILL.md yok)

- [ ] **Step 3: `.claude/skills/muze/SKILL.md` yaz**

````markdown
---
name: muze
description: Bir şehrin en popüler müzelerinde insanların ne kadar süre geçirdiğini web'den (Google/TripAdvisor süre özetleri, Reddit, bloglar) araştırır, kaynaklarıyla museumdb'ye kaydeder ve tablo olarak gösterir. Kullanım /muze <şehir> [--yenile]
argument-hint: <şehir> [--yenile]
---

# /muze — Müze süre veritabanı

Girdi: `$ARGUMENTS` → şehir adı ve isteğe bağlı `--yenile`.

Veri dosyalarına (`data/`) **yalnızca CLI ile** dokun; elle düzenleme, `cat >` ile yazma yok.
CLI (repo kökünden): `.venv/bin/python -m museumdb.cli <komut> <slug>`
Çıkış kodları: 0 tamam, 1 kayıt yok, 2 geçersiz girdi (stderr'deki `error:` mesajını oku).

## Kurallar

- Hiçbir değer kaynaksız yazılmaz. Bulamadığın değer `null`; tahmin etme, uydurma.
- Kaynak adları yalnızca: `google`, `tripadvisor`, `reddit`, `blog`, `official`, `wikidata`, `osm`.
- `signals[].value` kaynağın söylediği metnin birebir aynısı ("More than 3 hours", "People typically spend 1.5 hours here"). Yorumlama, birim çevirme.
- Tarihler `YYYY-MM-DD`, bugünün tarihi.
- Şehir başına en fazla 15 müze; ilk çalıştırmada 10–15.
- Notlar (`duration.notes`) Türkçe ve kısa; adlar İngilizce (`name`) + yerel (`name_local`).
- `typical_min_h`, `typical_max_h`, `fast_h`, `thorough_h`, `confidence` alanlarını yazma; `save` bunları sinyallerden hesaplar.
- `user_notes`'a dokunma; yeni müzede `[]`.
- Bulunamayan alan: `{"value": null, "source": null, "checked": "<bugün>"}` ("bakıldı, bulunamadı"). Hiç bakmadığın alanı taslağa koyma.
- Bir sayfa engellerse (403, bot koruması) arama sonucu özetiyle yetin; sayfayı zorlama.

## Adım 0 — Şehri çözümle

WebFetch: `https://www.wikidata.org/w/api.php?action=wbsearchentities&search=<şehir>&language=en&type=item&format=json&limit=5`

- Açıklaması şehir olan adayları al (city, capital, municipality, commune…).
- Birden çok makul aday varsa (ör. Paris, France / Paris, Texas) AskUserQuestion ile sor.
- `slug`: İngilizce adın küçük harfli ASCII hali, boşluk yerine tek tire (New York → `new-york`, Köln → `cologne`, İstanbul → `istanbul`).
- Ülke kodu: ISO 3166-1 alpha-2 (`IT`, `FR`, `TR`).

## Adım 1 — Önbellek

`.venv/bin/python -m museumdb.cli get <slug>`

- Çıkış 1 (kayıt yok) → Adım 2.
- `--yenile` verildiyse → Adım 2 (mevcut kayıttaki müze kimliklerini yeniden kullan).
- Aksi halde `.venv/bin/python -m museumdb.cli stale <slug>`:
  - `[]` → Adım 6.
  - Değilse yalnızca listedeki alanları (ör. `volatile.price`) Adım 3–4'teki yöntemle tazele. `get` çıktısını taslak olarak al, **yalnızca** bu alanları değiştir (`duration`'a dokunma), Adım 5.

## Adım 2 — Müze listesi

1. Wikidata SPARQL (WebFetch, `https://query.wikidata.org/sparql?format=json&query=<URL-kodlu sorgu>`), `<QID>` şehrin kimliği:
   ```sparql
   SELECT ?m ?mLabel ?local ?coord ?website ?sitelinks WHERE {
     ?m wdt:P31/wdt:P279* wd:Q33506 ;
        wdt:P131* wd:<QID> ;
        wikibase:sitelinks ?sitelinks .
     OPTIONAL { ?m wdt:P625 ?coord . }
     OPTIONAL { ?m wdt:P856 ?website . }
     OPTIONAL { ?m wdt:P1705 ?local . }
     SERVICE wikibase:label { bd:serviceParam wikibase:language "en" . }
   } ORDER BY DESC(?sitelinks) LIMIT 40
   ```
   Zaman aşımında `wdt:P131*` yerine `wdt:P131` dene. `coords` = `[enlem, boylam]` (WKT `Point(boylam enlem)` sırasını çevir!).
2. WebSearch: `top museums in <city>` (+ `most visited museums <city>`). İlk 10–15'i popülerliğe göre sırala (`popularity_rank` 1'den başlar). Arama sonuçları zayıfsa Wikidata `sitelinks` sırası.
3. Listede olup Wikidata sorgusunda çıkmayan müzeleri (ör. Roma için Vatikan Müzeleri, idari olarak Vatikan'da) ada göre ayrıca Wikidata'da ara.
4. Kimlik: Wikidata `Q…`; yoksa OSM `osm:way/123`; o da yoksa `slug:<şehir-slug>/<müze-slug>`.
5. `category`: kısa İngilizce etiketler (`art`, `history`, `archaeology`, `science`, `religious`, …).

## Adım 3 — Süre sinyalleri (müze başına)

1. WebSearch: `"<müze adı>" how long to spend` ve `"<müze adı>" tripadvisor`.
2. Google'ın "People typically spend …" özeti görünüyorsa → `source: "google"`, `url: null`.
3. TripAdvisor "Suggested duration" görünüyorsa → `source: "tripadvisor"`, metin aynen.
4. 2–3 Reddit/yorum/blog parçası: süre söylüyorsa sinyal olarak ekle (`reddit` / `blog`, `url` dolu); kalabalık saatler (`planning.busiest`), kuyruk süresi dakika aralığı (`planning.queue_min`, ör. `"60–120"`) ve Türkçe bağlam notları (`duration.notes`, ör. "Sesli rehberle +1 saat") çıkar.
5. Hiç sinyal yoksa `duration: null`.

## Adım 4 — Resmi site

Müzenin resmi sitesinden: `volatile.price` (yetişkin bilet, para birimiyle, ör. `"€20 adult"`), `volatile.hours` (OSM `opening_hours` biçimine yakın, ör. `"Mo–Sa 08:00–19:00"`), `planning.advance_ticket` (`required` / `strongly_recommended` / `recommended` / `not_needed`). `source: "official"`. Okunamazsa `null` + `checked`; uydurma yok. Saatler sitede yoksa Wikidata/OSM `opening_hours` (`source: "wikidata"` / `"osm"`).

## Adım 5 — Kaydet

Taslağı scratchpad dizinine yaz, sonra:
`.venv/bin/python -m museumdb.cli save <slug> < <taslak-dosyası>`

- Çıkış 2 → `error:` mesajındaki yolu (ör. `museums/3/coords`) düzelt, tekrar dene (en fazla 2 kez). Hâlâ hata varsa mesajı kullanıcıya göster; kayıt yazılmamıştır, eski dosya sağlamdır.
- Mevcut kayıtla birleştirme `save` içinde yapılır: gelen `null` dolu değeri ezmez, aynı kaynaklı sinyaller yenisiyle değişir, `user_notes` korunur.

## Adım 6 — Göster

`.venv/bin/python -m museumdb.cli table <slug>` çıktısını kod bloğunda göster. Altına 1–2 cümle: hangi müzelerde veri yok/düşük güven, hangi kaynaklar engellendi.

## Taslak örneği

```json
{
  "schema_version": 1,
  "city": {"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220", "queried_at": "2026-10-01"},
  "museums": [
    {
      "id": "Q182955",
      "name": "Vatican Museums",
      "name_local": "Musei Vaticani",
      "category": ["art", "history"],
      "popularity_rank": 1,
      "address": "Viale Vaticano, 00165 Roma",
      "coords": [41.9065, 12.4536],
      "website": "https://www.museivaticani.va",
      "user_notes": [],
      "duration": {
        "signals": [
          {"source": "google", "value": "3–4 h", "url": null, "checked": "2026-10-01"},
          {"source": "tripadvisor", "value": "More than 3 hours", "url": null, "checked": "2026-10-01"},
          {"source": "reddit", "value": "~5 h with audio guide", "url": "https://www.reddit.com/r/rome/comments/example", "checked": "2026-10-01"}
        ],
        "notes": ["Sesli rehberle +1 saat"]
      },
      "planning": {
        "busiest": {"value": "Sa–Ça 10:00–13:00", "source": "google", "checked": "2026-10-01"},
        "queue_min": {"value": "60–120", "source": "reddit", "checked": "2026-10-01"},
        "advance_ticket": {"value": "strongly_recommended", "source": "official", "checked": "2026-10-01"}
      },
      "volatile": {
        "price": {"value": "€20 adult", "source": "official", "checked": "2026-10-01"},
        "hours": {"value": null, "source": null, "checked": "2026-10-01"}
      }
    }
  ]
}
```
````

- [ ] **Step 4: Testlerin geçtiğini gör**

Run: `.venv/bin/python -m pytest tests/test_skill_doc.py -v`
Expected: 2 passed

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/muze/SKILL.md tests/test_skill_doc.py
git commit -m "feat: /muze skill for researching museum durations" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```

---

### Task 10: Roma ile manuel deneme ve spec güncellemesi

Web toplama otomatik test edilmez (spec Bölüm 7); bu görev başarı ölçütlerini elle doğrular.

**Files:**
- Create: `data/cities/rome.json`, `data/index.json` (CLI üretir)
- Modify: `docs/superpowers/specs/2026-10-01-museum-duration-db-design.md` (Bölüm 3 örneği, Bölüm 5 kod yapısı, Bölüm 9)

**Interfaces:**
- Consumes: `/muze` skill'i (Task 9), CLI (Task 8)
- Produces: ilk gerçek veri + kaynak deneme bulguları

- [ ] **Step 1: Skill'in göründüğünü doğrula**

Claude Code'u repo kökünde yeniden başlat (proje skill'leri oturum başında yüklenir). `/muze` komut listesinde görünmeli.

- [ ] **Step 2: İlk çalıştırma**

`/muze Rome` çalıştır. Beklenen (spec başarı ölçütü 1): 10–15 müze; her birinde süre aralığı, güven, kaynaklar ve notlar; sonda tablo.
Kontrol:
```bash
.venv/bin/python -m museumdb.cli table rome
.venv/bin/python -c "import json; d=json.load(open('data/cities/rome.json')); print(len(d['museums'])); print(sum(1 for m in d['museums'] for s in (m['duration'] or {}).get('signals', []) if not s['source']))"
```
Expected: ilk satır 10–15 arası; ikinci satır `0` (kaynaksız sinyal yok).

- [ ] **Step 3: Önbellek davranışı**

`/muze Rome` tekrar çalıştır. Beklenen (başarı ölçütü 2): web araması yapılmadan tablo gösterilir; `stale` yalnızca hiç bakılmamış alanları listeler (varsa yalnızca onlar tazelenir). `git diff --stat data/` yalnızca tazelenen alanları göstermeli.

- [ ] **Step 4: Bulguları spec'e işle**

Spec Bölüm 9'u doldur — her kaynak (`google`, `tripadvisor`, `reddit`, `blog`, `official`, `wikidata`, `osm`) için: erişilebilir miydi, hangi alanları verdi, güvenilirlik gözlemi, ayrıştırılamayan süre metni örnekleri (varsa `parse_duration`'a eklenecek biçimler için not).
Ayrıca spec'e bu planın "Spec'ten bilinçli sapmalar" listesini işle: Bölüm 3 örneğinde `city` nesnesine `"slug": "rome"` ekle; Bölüm 5 kod yapısına `validation.py`, `merge.py`, `table.py` satırlarını ekle; Bölüm 3 Kurallar'a sapma 3–6'yı birer madde olarak ekle.

- [ ] **Step 5: Commit**

```bash
git add data/ docs/superpowers/specs/2026-10-01-museum-duration-db-design.md
git commit -m "data: first Rome run; record source trial findings in spec" -m "Co-Authored-By: Claude Opus 5.5 (1M context) <noreply@anthropic.com>"
```
