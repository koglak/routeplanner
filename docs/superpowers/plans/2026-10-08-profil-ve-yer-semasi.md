# Gezgin Profili ve Yer Şeması (Plan 1/6) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Kullanıcının gezme tarzını `profil.md`'ye yazmak ve `museumdb` veritabanını müze-merkezli şemadan (v1, `museums`) türü olan genel **Yer** şemasına (v2, `places`) taşımak; Önem, Semt ve Günübirlik alanlarını eklemek.

**Architecture:** `Museum` sınıfı `Place` olur ve zorunlu bir `type` alanı kazanır. v1 belgeleri okunurken `migrate.upgrade` ile bellekte v2'ye çevrilir, böylece eski dosyalar ve eski taslaklar çalışmaya devam eder; `migrate` komutu diskteki dosyaları kalıcı olarak yükseltir. `importance` hiçbir zaman elle yazılmaz: `save` sırasında `importance_evidence`'tan `importance.classify` ile hesaplanır.

**Tech Stack:** Python 3.11, stdlib, `jsonschema>=4.18`, pytest.

**Spec:** `docs/superpowers/specs/2026-10-08-gezi-planlayici-design.md` (Bölüm 3, 4, 5'teki `migrate`, 8'deki adım 1–2). Sözlük: `CONTEXT.md`. Karar: `docs/adr/0001-muzeden-yere-genelleme.md`.

**Bu planın dışında kalanlar (sonraki planlar):** `restaurants` / `dishes` / `activities` dizileri (Plan 3–4; v2'ye isteğe bağlı diziler olarak eklenecek, sürüm artmayacak), `/yer` skill'i ve türe göre tablo (Plan 2), `--kind` parametresi, rota CLI'ı (Plan 5), `/gezi` (Plan 6). Spec'teki `migrate [<slug>]` burada argümansız: veri dizinindeki tüm dosyaları yükseltir.

## Global Constraints

- Yeni kodda yorum, docstring ya da JSDoc yok. Var olan yorum ve docstring'lere dokunma, silme (kullanıcının global kuralı).
- Python 3.11+; yeni bağımlılık yok (`jsonschema` dışında).
- Hiçbir değer kaynaksız yazılmaz; bulunamayan değer `null`.
- `data/` altına yalnızca CLI ile yazılır.
- Çıkış kodları: `0` tamam, `1` kayıt yok, `2` geçersiz girdi, `3` ağ hatası.
- Kaynak adları yalnızca: `google`, `tripadvisor`, `reddit`, `blog`, `official`, `wikidata`, `osm`.
- `schema_version` artık `2`; v1 belgeler okunur ama yazılmaz.
- Yer türleri: `museum`, `religious`, `square`, `monument`, `viewpoint`, `bazaar`, `park`, `district`, `daytrip`, `other`.
- Önem düzeyleri: `must`, `recommended`, `optional`.
- Testler: `.venv/bin/pytest` (repo kökünden). Başlangıçta 173 test geçiyor.

## Review Focus

1. Diskte `migrate` çalıştırılmamış v1 dosyası varken `get` / `table` / `serve` → hata vermeden v2 olarak okunmalı (Task 2: `test_reads_v1_file_from_disk`).
2. Eski `/muze` oturumundan ya da ajandan gelen v1 taslağı `save`'e verilirse → kabul edilmeli, v2 olarak kaydedilmeli (Task 2: `test_save_accepts_v1_draft`).
3. `index.json`'da eski `museum_count` anahtarı varken `list_cities` / web arayüzü → çökmemeli (Task 4: `test_list_cities_reads_old_index`).
4. `migrate` iki kez çalıştırılırsa → ikincisi hiçbir dosyaya dokunmamalı (Task 4: `test_migrate_is_idempotent`).
5. Yeniden araştırmada taslakta `importance_evidence` yoksa → eski kanıt ve hesaplanan Önem korunmalı (Task 3: `test_missing_evidence_keeps_previous_importance`).

---

### Task 1: Gezgin Profili (`profil.md`)

**Files:**
- Create: `profil.md`
- Test: `tests/test_profile.py`

**Interfaces:**
- Produces: `profil.md`, satırları `- <anahtar>: <değer>` biçiminde. Plan 6'daki `/gezi` bu anahtarları okuyacak: `gun_baslangic`, `gun_bitis`, `yuruyus_hizi_kmh`, `sokak_payi`, `toplu_tasima_esigi_km`, `muze_suresi`, `gunde_en_fazla_muze`, `ugrak_turleri`, `kahvalti`, `ogle`, `aksam`, `restoran_yakinlik_dk`, `restoran_en_dusuk_puan`.

- [ ] **Step 1: Write the failing test**

`tests/test_profile.py`:

```python
import re
from pathlib import Path

PROFILE = Path(__file__).resolve().parents[1] / "profil.md"
REQUIRED_KEYS = (
    "gun_baslangic", "gun_bitis", "yuruyus_hizi_kmh", "sokak_payi", "toplu_tasima_esigi_km",
    "muze_suresi", "gunde_en_fazla_muze", "ugrak_turleri", "kahvalti", "ogle", "aksam",
    "restoran_yakinlik_dk", "restoran_en_dusuk_puan",
)
PLACE_TYPES = {"museum", "religious", "square", "monument", "viewpoint", "bazaar", "park", "district",
               "daytrip", "other"}


def profile_values():
    pairs = re.findall(r"^- ([a-z_]+): (.+)$", PROFILE.read_text(encoding="utf-8"), re.M)
    return dict(pairs)


def test_profile_has_every_key_the_planner_reads():
    assert set(REQUIRED_KEYS) <= set(profile_values())


def test_times_are_hh_mm():
    values = profile_values()
    for key in ("gun_baslangic", "gun_bitis"):
        assert re.fullmatch(r"\d{2}:\d{2}", values[key]), key
    for key in ("kahvalti", "ogle", "aksam"):
        assert re.fullmatch(r"\d{2}:\d{2} \(\d+ dk\)", values[key]), key


def test_numbers_parse():
    values = profile_values()
    for key in ("yuruyus_hizi_kmh", "sokak_payi", "toplu_tasima_esigi_km", "restoran_en_dusuk_puan"):
        float(values[key])
    for key in ("gunde_en_fazla_muze", "restoran_yakinlik_dk"):
        int(values[key])


def test_museum_duration_choice_and_stopover_types():
    values = profile_values()
    assert values["muze_suresi"] in ("hizli", "detayli")
    assert {t.strip() for t in values["ugrak_turleri"].split(",")} <= PLACE_TYPES
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_profile.py -v`
Expected: FAIL with `FileNotFoundError` (profil.md yok).

- [ ] **Step 3: Write `profil.md`**

Değerler mevcut `hizli-gezgin` skill'inden ve grilling oturumundaki kararlardan geliyor:

```markdown
# Gezgin Profili

`/gezi` her planlamada bu dosyayı okur. Değerleri istediğin zaman değiştirebilirsin; `- anahtar: değer`
satırlarının biçimini koru.

## Tempo

Hızlı gezerim: boş saat istemem, en önemli yerleri kaçırmak istemem.

- gun_baslangic: 08:00
- gun_bitis: 22:00
- gunde_en_fazla_muze: 2

Boşluk kalırsa yakındaki opsiyonel bir Yer, semt yürüyüşü, seyir noktası, çarşı ya da akşam aktivitesiyle
doldur. Beklemek yerine bir sonraki noktaya yürüyerek geçmeyi tercih et.

## Yürüyüş

- yuruyus_hizi_kmh: 5
- sokak_payi: 1.3
- toplu_tasima_esigi_km: 2.5

Eşiği aşan geçişlerde toplu taşıma ya da taksi öner ve süresini yaz. Yokuşlu şehirlerde ek pay ver.

## Müze

- muze_suresi: hizli

Planlamada müze listesini göster; detaylı gezmek istediklerimi ben seçeyim, onlarda Detaylı Süre'yi kullan.

## Uğrak

- ugrak_turleri: religious, square, monument

Bu türlerdeki Yer'ler varsayılan olarak Uğrak'tır: içine girmeden, Yürüyüş Turu üzerinde kısa duruş.
Önem'i `must` olan Yer (ör. Ayasofya) istisnadır, içine girilir. Sınırda kalanları bana sor.

## Öğünler

- kahvalti: 08:00 (45 dk)
- ogle: 13:00 (60 dk)
- aksam: 19:30 (90 dk)
- restoran_yakinlik_dk: 10
- restoran_en_dusuk_puan: 4.3

Saatleri yerel kültüre göre kaydır (ör. İspanya'da akşam 21:00). Turist tuzağı olarak yorumlanan yerleri ele.
Yemek önerisinde o yerde iyi yapılan Geleneksel Yemek'i de söyle.

## Sıralama

- Kalabalık yerler açılışta, günün ilk durağı.
- Seyir noktaları gün batımına.
- Kapalı güne o Yer'i koyma.

## Sevdiklerim / sevmediklerim

- sevilen_turler: viewpoint, district, bazaar
- sevilmeyen_turler: yok
```

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv/bin/pytest tests/test_profile.py -v`
Expected: 4 passed.

- [ ] **Step 5: Kullanıcıyla değerleri gözden geçir**

Kullanıcıya `profil.md`'yi göster ve özellikle şunları sor: `gunde_en_fazla_muze` (2 mi?), `sevilen_turler` / `sevilmeyen_turler`, öğün süreleri. Verdiği değerleri dosyaya yaz, Step 4'ü tekrar çalıştır.

- [ ] **Step 6: Commit**

```bash
git add profil.md tests/test_profile.py
git commit -m "feat: gezgin profili (profil.md)"
```

---

### Task 2: `Museum` → `Place`, şema v2 ve v1 okuma

**Files:**
- Create: `museumdb/migrate.py`, `tests/test_migrate.py`
- Modify: `museumdb/models.py`, `museumdb/schema.json`, `museumdb/validation.py`, `museumdb/merge.py`, `museumdb/store.py`, `museumdb/scaffold.py`, `museumdb/table.py`, `museumdb/cli.py`, `museumdb/web_static/app.js`
- Modify tests: `tests/conftest.py`, `tests/test_models.py`, `tests/test_validation.py`, `tests/test_merge.py`, `tests/test_store.py`, `tests/test_cli.py`, `tests/test_scaffold.py`, `tests/test_table.py`, `tests/test_web.py`

**Interfaces:**
- Produces:
  - `museumdb.models.SCHEMA_VERSION = 2`, `PLACE_TYPES: tuple[str, ...]`
  - `museumdb.models.Place` (eski `Museum`; alanları aynı + `type: str`, `id`, `name`'den hemen sonra zorunlu)
  - `museumdb.models.City.places: list[Place]` (eski `museums`)
  - `museumdb.models.CityIndexEntry.place_count: int` (eski `museum_count`)
  - `museumdb.migrate.upgrade(data: object) -> object` — v1 sözlüğü v2'ye çevirir (kopya), diğer her şeyi olduğu gibi döndürür
  - `museumdb.migrate.upgrade_index_entry(entry: dict) -> dict` — `museum_count` → `place_count`
  - `validation.parse_city` v1 kabul eder; çift id hatası `"duplicate place ids: ..."`
  - CLI JSON çıktısında `museum_id` → `place_id`; `save` çıktısı `"saved <slug>: <n> places"`

- [ ] **Step 1: Test fixture'larını v2'ye çevir**

`tests/conftest.py` içinde:
- `"schema_version": 1,` → `"schema_version": 2,`
- `"museums": [` → `"places": [`
- `"name": "Vatican Museums",` satırından sonra `"type": "museum",` ekle; `"name": "Borghese Gallery",` satırından sonra da `"type": "museum",` ekle.
- Dosyanın sonuna ekle:

```python
@pytest.fixture
def rome_v1_dict():
    d = copy.deepcopy(ROME)
    d["schema_version"] = 1
    museums = d.pop("places")
    for m in museums:
        for key in ("type", "importance", "importance_evidence", "highlights", "transport"):
            m.pop(key, None)
    d["museums"] = museums
    return d
```

Diğer testlerdeki adları toplu değiştir (`test_wikidata.py` hariç; o dosya Wikidata fonksiyonlarını test ediyor ve değişmiyor):

```bash
cd tests && sed -i '' \
  -e 's/\["museums"\]/["places"]/g' \
  -e 's/\.museums/.places/g' \
  -e 's/"museum_id"/"place_id"/g' \
  -e 's/museum_count/place_count/g' \
  -e 's/2 museums/2 places/g' \
  -e 's/duplicate museum ids/duplicate place ids/g' \
  test_models.py test_validation.py test_merge.py test_store.py test_cli.py test_scaffold.py test_table.py test_web.py && cd ..
```

Elle düzelt:
- `tests/test_models.py`: import satırında `Museum` → `Place`; `test_minimal_museum_gets_defaults` içinde `Museum.from_dict({"id": "Q1", "name": "X"})` → `Place.from_dict({"id": "Q1", "name": "X", "type": "museum"})` ve sona `assert m.type == "museum"` ekle.
- `tests/test_merge.py`: `{"id": "Q999002", "name": "Capitoline Museums", "popularity_rank": 3}` → `{"id": "Q999002", "name": "Capitoline Museums", "type": "museum", "popularity_rank": 3}`; `test_museums_sorted_by_rank_unranked_last` içindeki üç sözlüğün her birine `"type": "museum"` ekle.
- `tests/test_validation.py`: `(lambda d: d.update(schema_version=2), "schema_version"),` → `(lambda d: d.update(schema_version=3), "schema_version"),`; listenin sonuna şunları ekle:

```python
        (lambda d: _vatican(d).update(type="castle"), "castle"),
        (lambda d: _vatican(d).pop("type"), "type"),
```

- `tests/test_scaffold.py`: `test_build_draft_...` içindeki beklenen müze sözlüğüne `"type": "museum",` ekle.

- [ ] **Step 2: Yeni testleri yaz**

`tests/test_migrate.py`:

```python
import copy

from museumdb.migrate import upgrade, upgrade_index_entry
from museumdb.validation import parse_city


def test_upgrade_moves_museums_to_places_as_museum_type(rome_v1_dict):
    upgraded = upgrade(rome_v1_dict)
    assert upgraded["schema_version"] == 2
    assert "museums" not in upgraded
    assert [p["type"] for p in upgraded["places"]] == ["museum", "museum"]
    assert upgraded["places"][0]["name"] == "Vatican Museums"


def test_upgrade_does_not_modify_its_input(rome_v1_dict):
    before = copy.deepcopy(rome_v1_dict)
    upgrade(rome_v1_dict)
    assert rome_v1_dict == before


def test_upgrade_returns_current_version_as_is(rome_dict):
    assert upgrade(rome_dict) is rome_dict


def test_upgrade_returns_non_dict_as_is():
    assert upgrade([1, 2]) == [1, 2]


def test_parse_city_accepts_v1(rome_v1_dict, rome_dict):
    assert parse_city(rome_v1_dict).to_dict() == rome_dict


def test_upgrade_index_entry_renames_count():
    old = {"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220",
           "queried_at": "2026-10-01", "museum_count": 12}
    assert upgrade_index_entry(old) == {"slug": "rome", "name": "Rome", "country": "IT",
                                        "wikidata_id": "Q220", "queried_at": "2026-10-01",
                                        "place_count": 12}
    assert "museum_count" in old


def test_upgrade_index_entry_keeps_new_entries():
    entry = {"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220",
             "queried_at": "2026-10-01", "place_count": 12}
    assert upgrade_index_entry(entry) == entry
```

`tests/test_store.py` sonuna:

```python
def test_reads_v1_file_from_disk(tmp_path, rome_v1_dict, rome_dict):
    path = tmp_path / "cities" / "rome.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(rome_v1_dict), encoding="utf-8")
    assert make_store(tmp_path).get_city("rome").to_dict() == rome_dict
```

`tests/test_cli.py` sonuna:

```python
def test_save_accepts_v1_draft(run, rome_v1_dict):
    code, out, _ = run("save", "rome", stdin=json.dumps(rome_v1_dict))
    assert code == 0 and out.strip() == "saved rome: 2 places"
    code, out, _ = run("get", "rome")
    stored = json.loads(out)
    assert stored["schema_version"] == 2 and [p["type"] for p in stored["places"]] == ["museum", "museum"]
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest -q`
Expected: çok sayıda FAIL (`ModuleNotFoundError: museumdb.migrate`, `places` anahtarı tanınmıyor, `schema_version` 2 reddediliyor).

- [ ] **Step 4: `museumdb/migrate.py`**

```python
from __future__ import annotations

import copy


def upgrade(data: object) -> object:
    if not isinstance(data, dict) or data.get("schema_version") != 1:
        return data
    upgraded = copy.deepcopy(data)
    upgraded["schema_version"] = 2
    museums = upgraded.pop("museums", [])
    upgraded["places"] = [{**m, "type": "museum"} if isinstance(m, dict) else m for m in museums]
    return upgraded


def upgrade_index_entry(entry: dict) -> dict:
    if "museum_count" not in entry:
        return entry
    upgraded = {k: v for k, v in entry.items() if k != "museum_count"}
    upgraded["place_count"] = entry["museum_count"]
    return upgraded
```

- [ ] **Step 5: `museumdb/models.py`**

- `SCHEMA_VERSION = 1` → `SCHEMA_VERSION = 2`
- `VOLATILE_FIELDS` satırından sonra ekle:

```python
PLACE_TYPES = ("museum", "religious", "square", "monument", "viewpoint", "bazaar", "park", "district", "daytrip",
               "other")
```

- `class Museum:` → `class Place:`; `name: str` satırından sonra `type: str` ekle.
- `def from_dict(cls, d: dict) -> Museum:` → `-> Place:`; `return cls(` içinde `name=d["name"],` satırından sonra `type=d["type"],` ekle.
- `City` içinde: `museums: list[Museum] = field(default_factory=list)` → `places: list[Place] = field(default_factory=list)`; `to_dict` içinde `"museums": [asdict(m) for m in self.museums],` → `"places": [asdict(p) for p in self.places],`; `from_dict` içinde `museums=[Museum.from_dict(m) for m in d.get("museums", [])],` → `places=[Place.from_dict(p) for p in d.get("places", [])],`.
- `CityIndexEntry` içinde `museum_count: int` → `place_count: int`.

- [ ] **Step 6: `museumdb/schema.json`**

- `"title": "travelkardi city museum durations"` → `"title": "travelkardi city places"`
- `"required": ["schema_version", "city", "museums"],` → `"required": ["schema_version", "city", "places"],`
- `"schema_version": {"const": 1},` → `"schema_version": {"const": 2},`
- `"museums": {"type": "array", "items": {"$ref": "#/$defs/museum"}}` → `"places": {"type": "array", "items": {"$ref": "#/$defs/place"}}`
- `$defs` içinde `"museum": {` → `"place": {`; onun `"required": ["id", "name"],` → `"required": ["id", "name", "type"],`; `"name": {"type": "string", "minLength": 1},` satırından sonra (place içinde) ekle:

```json
        "type": {"enum": ["museum", "religious", "square", "monument", "viewpoint", "bazaar", "park", "district", "daytrip", "other"]},
```

- [ ] **Step 7: `museumdb/validation.py`**

- Import ekle: `from museumdb.migrate import upgrade`
- `validate_city_dict` içinde `ids = [m["id"] for m in data["museums"]]` → `ids = [p["id"] for p in data["places"]]`; `f"duplicate museum ids: ..."` → `f"duplicate place ids: {', '.join(duplicates)}"`.
- `parse_city`:

```python
def parse_city(data: dict) -> City:
    upgraded = upgrade(data)
    validate_city_dict(upgraded)
    return City.from_dict(upgraded)
```

- [ ] **Step 8: `museumdb/merge.py`**

- Import: `from museumdb.models import City, Duration, FieldValue, Place`
- `SCALAR_FIELDS = ("name", "name_local", "popularity_rank", "address", "coords", "website")` → `SCALAR_FIELDS = ("name", "type", "name_local", "popularity_rank", "address", "coords", "website")`
- `merge_city` içinde tüm `result.museums` → `result.places`, `incoming.museums` → `incoming.places`, döngü değişkeni `museum` → `place`, `_merge_museum(current, museum)` → `_merge_place(current, place)`.
- `def _merge_museum(current: Museum, incoming: Museum) -> None:` → `def _merge_place(current: Place, incoming: Place) -> None:` (gövde aynı, içindeki yorum satırı kalır).

- [ ] **Step 9: `museumdb/store.py`**

- Import ekle: `from museumdb.migrate import upgrade_index_entry`
- `stale_fields` içinde `for museum in city.museums:` → `for place in city.places:`, `getattr(museum, group)` → `getattr(place, group)`, `stale.append((museum.id, ...))` → `stale.append((place.id, f"{group}.{name}"))`.
- `list_cities` dönüşü: `return [CityIndexEntry(**upgrade_index_entry(e)) for e in json.loads(self._index_path.read_text(encoding="utf-8"))]`
- `_update_index` içinde `museum_count=len(city.museums),` → `place_count=len(city.places),`.

- [ ] **Step 10: `museumdb/scaffold.py`, `museumdb/table.py`, `museumdb/cli.py`, `app.js`**

`scaffold.py`:
- `entry = {"id": museum["id"], **{k: museum[k] for k in IDENTITY_FIELDS}}` → `entry = {"id": museum["id"], "type": "museum", **{k: museum[k] for k in IDENTITY_FIELDS}}`
- dönen sözlükte `"museums": entries,` → `"places": entries,`

`table.py`:
- `from museumdb.models import City, Museum` → `from museumdb.models import City, Place`
- `city.museums` → `city.places` (iki yer), `m: Museum` → `m: Place` (dört fonksiyon imzası). Görünen metinler ("müze") bu planda değişmez.

`cli.py`:
- `_stale` ve `_status` içinde `{"museum_id": museum_id, "field": field} for museum_id, field in fields` → `{"place_id": place_id, "field": field} for place_id, field in fields`
- `_save` içinde `print(f"saved {args.slug}: {len(saved.museums)} museums")` → `print(f"saved {args.slug}: {len(saved.places)} places")`

`museumdb/web_static/app.js`:

```bash
sed -i '' -e 's/const { city, museums } = state.city;/const { city, places: museums } = state.city;/' \
  -e 's/\.museums/.places/g' -e 's/museum_count/place_count/g' museumdb/web_static/app.js
```

Sonra `grep -n "museums\|museum_count" museumdb/web_static/app.js` çalıştır: yalnızca yerel `museums` değişkeni kalmalı, `state.city.museums` ya da `museum_count` kalmamalı.

- [ ] **Step 11: Run all tests**

Run: `.venv/bin/pytest -q`
Expected: tümü PASS.

- [ ] **Step 12: Web arayüzünü elle doğrula**

Run: `.venv/bin/python -m museumdb.cli serve --port 8766` (arka planda), tarayıcıda ya da `curl -s http://127.0.0.1:8766/api/cities/istanbul | head -c 300` ile `places` geldiğini gör. Sayfa `http://127.0.0.1:8766` şehir listesini ve İstanbul müzelerini göstermeli (diskteki dosya hâlâ v1; okuma sırasında yükseltiliyor). Sunucuyu durdur.

- [ ] **Step 13: Commit**

```bash
git add museumdb tests
git commit -m "feat: Museum -> Place, schema v2 with place type; v1 documents upgraded on read"
```

---

### Task 3: Önem, Semt ve Günübirlik alanları

**Files:**
- Create: `museumdb/importance.py`, `tests/test_importance.py`
- Modify: `museumdb/models.py`, `museumdb/schema.json`, `museumdb/validation.py`, `museumdb/merge.py`, `tests/conftest.py`, `tests/test_merge.py`, `tests/test_validation.py`, `tests/test_models.py`

**Interfaces:**
- Consumes: `Place`, `PLACE_TYPES`, `merge_city` (Task 2)
- Produces:
  - `models.IMPORTANCE_LEVELS = ("must", "recommended", "optional")`
  - `models.ImportanceEvidence(checked: str, blog_mentions: int | None = None, review_count: int | None = None, review_source: str | None = None, urls: list[str] = [])`
  - `models.Highlight(name: str, coords: list[float] | None = None)`
  - `models.Transport(checked: str, mode: str | None = None, departure: str | None = None, one_way_min: int | None = None, last_return: str | None = None, source: str | None = None, url: str | None = None)`
  - `Place` yeni alanlar: `importance: str | None = None`, `importance_evidence: ImportanceEvidence | None = None`, `highlights: list[Highlight] = []`, `transport: Transport | None = None`
  - `importance.classify(evidence: ImportanceEvidence | None) -> str | None`
  - Eşikler: `MUST_BLOG_MENTIONS = 4`, `MUST_REVIEW_COUNT = 20000`, `RECOMMENDED_BLOG_MENTIONS = 2`, `RECOMMENDED_REVIEW_COUNT = 3000` (ilk değerler; Plan 2'de İstanbul verisiyle kalibre edilecek)
  - Kurallar: `importance` her `save`'de kanıttan yeniden hesaplanır; `highlights` yalnızca `district`, `transport` yalnızca `daytrip` türünde olabilir.

- [ ] **Step 1: Fixture'a yeni alanları ekle**

`tests/conftest.py` içinde her iki yerin (`Vatican Museums` ve `Borghese Gallery`) `"type": "museum",` satırından sonra ekle:

```python
            "importance": None,
            "importance_evidence": None,
            "highlights": [],
            "transport": None,
```

- [ ] **Step 2: Write the failing tests**

`tests/test_importance.py`:

```python
import pytest

from museumdb.importance import classify
from museumdb.models import ImportanceEvidence


def evidence(blogs=None, reviews=None):
    return ImportanceEvidence(checked="2026-10-08", blog_mentions=blogs, review_count=reviews)


@pytest.mark.parametrize(
    "blogs, reviews, expected",
    [
        (4, None, "must"),
        (None, 20000, "must"),
        (1, 25000, "must"),
        (3, 19999, "recommended"),
        (2, None, "recommended"),
        (None, 3000, "recommended"),
        (1, 2999, "optional"),
        (0, 0, "optional"),
    ],
)
def test_thresholds(blogs, reviews, expected):
    assert classify(evidence(blogs, reviews)) == expected


def test_no_evidence_means_unknown():
    assert classify(None) is None


def test_evidence_without_counts_means_unknown():
    assert classify(evidence()) is None
```

`tests/test_merge.py` sonuna:

```python
EVIDENCE = {"blog_mentions": 5, "review_count": 1200, "review_source": "google",
            "urls": ["https://example.com/top-10"], "checked": "2026-10-08"}


def test_importance_is_computed_from_evidence(rome_dict):
    rome_dict["places"][0]["importance_evidence"] = dict(EVIDENCE)
    rome_dict["places"][0]["importance"] = "optional"
    result = merge_city(None, _city(rome_dict))
    assert result.places[0].importance == "must"
    assert result.places[1].importance is None


def test_missing_evidence_keeps_previous_importance(rome_dict):
    rome_dict["places"][0]["importance_evidence"] = dict(EVIDENCE)
    inc = copy.deepcopy(rome_dict)
    inc["places"][0]["importance_evidence"] = None
    result = _merge(rome_dict, inc).places[0]
    assert result.importance_evidence.blog_mentions == 5
    assert result.importance == "must"


def test_new_evidence_replaces_old(rome_dict):
    rome_dict["places"][0]["importance_evidence"] = dict(EVIDENCE)
    inc = copy.deepcopy(rome_dict)
    inc["places"][0]["importance_evidence"] = {**EVIDENCE, "blog_mentions": 1, "review_count": 10}
    assert _merge(rome_dict, inc).places[0].importance == "optional"


def test_highlights_and_transport_replaced_only_when_given():
    district = {"id": "slug:istanbul/balat", "name": "Balat", "type": "district",
                "highlights": [{"name": "Fener Rum Lisesi", "coords": [41.029, 28.949]}]}
    daytrip = {"id": "slug:istanbul/buyukada", "name": "Büyükada", "type": "daytrip",
               "transport": {"mode": "ferry", "departure": "Kabataş", "one_way_min": 95, "last_return": "21:00",
                             "source": "official", "url": None, "checked": "2026-10-08"}}
    city = {"schema_version": 2,
            "city": {"slug": "istanbul", "name": "Istanbul", "queried_at": "2026-10-08"},
            "places": [district, daytrip]}
    incoming = copy.deepcopy(city)
    incoming["places"][0]["highlights"] = []
    incoming["places"][1]["transport"] = None
    result = _merge(city, incoming)
    assert [h.name for h in result.places[0].highlights] == ["Fener Rum Lisesi"]
    assert result.places[1].transport.one_way_min == 95
```

`tests/test_validation.py` içindeki `test_rejects_invalid_documents` parametre listesinin sonuna ekle:

```python
        (lambda d: _vatican(d).update(importance="top"), "top"),
        (lambda d: _vatican(d).update(importance_evidence={"blog_mentions": -1, "checked": "2026-10-08"}), "-1"),
        (lambda d: _vatican(d).update(importance_evidence={"review_source": "yelp", "checked": "2026-10-08"}), "yelp"),
        (lambda d: _vatican(d).update(highlights=[{"coords": [41.0, 28.9]}]), "name"),
```

ve dosyanın sonuna:

```python
def test_highlights_only_on_districts(rome_dict):
    _vatican(rome_dict)["highlights"] = [{"name": "Sistine Chapel", "coords": None}]
    with pytest.raises(ValidationError, match="highlights are only allowed on district places: Q182955"):
        validate_city_dict(rome_dict)


def test_transport_only_on_daytrips(rome_dict):
    _vatican(rome_dict)["transport"] = {"mode": "bus", "checked": "2026-10-08"}
    with pytest.raises(ValidationError, match="transport is only allowed on daytrip places: Q182955"):
        validate_city_dict(rome_dict)


def test_district_with_highlights_is_valid(rome_dict):
    _vatican(rome_dict).update(type="district", highlights=[{"name": "Sistine Chapel", "coords": [41.903, 12.454]}])
    validate_city_dict(rome_dict)
```

`tests/test_models.py` içindeki `test_minimal_museum_gets_defaults` sonuna ekle:

```python
    assert m.importance is None and m.importance_evidence is None
    assert m.highlights == [] and m.transport is None
```

- [ ] **Step 3: Run tests to verify they fail**

Run: `.venv/bin/pytest -q`
Expected: FAIL — `ModuleNotFoundError: museumdb.importance`, `ImportanceEvidence` import hatası, şema `importance` alanını tanımıyor.

- [ ] **Step 4: `museumdb/models.py`**

`PLACE_TYPES` satırından sonra:

```python
IMPORTANCE_LEVELS = ("must", "recommended", "optional")
```

`Duration` sınıfından sonra, `Place`'ten önce:

```python
@dataclass
class ImportanceEvidence:
    checked: str
    blog_mentions: int | None = None
    review_count: int | None = None
    review_source: str | None = None
    urls: list[str] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> ImportanceEvidence:
        return cls(
            checked=d["checked"],
            blog_mentions=d.get("blog_mentions"),
            review_count=d.get("review_count"),
            review_source=d.get("review_source"),
            urls=list(d.get("urls", [])),
        )


@dataclass
class Highlight:
    name: str
    coords: list[float] | None = None

    @classmethod
    def from_dict(cls, d: dict) -> Highlight:
        coords = d.get("coords")
        return cls(name=d["name"], coords=list(coords) if coords is not None else None)


@dataclass
class Transport:
    checked: str
    mode: str | None = None
    departure: str | None = None
    one_way_min: int | None = None
    last_return: str | None = None
    source: str | None = None
    url: str | None = None

    @classmethod
    def from_dict(cls, d: dict) -> Transport:
        return cls(
            checked=d["checked"],
            mode=d.get("mode"),
            departure=d.get("departure"),
            one_way_min=d.get("one_way_min"),
            last_return=d.get("last_return"),
            source=d.get("source"),
            url=d.get("url"),
        )
```

`Place` içinde `volatile: dict[str, FieldValue] = field(default_factory=dict)` satırından sonra:

```python
    importance: str | None = None
    importance_evidence: ImportanceEvidence | None = None
    highlights: list[Highlight] = field(default_factory=list)
    transport: Transport | None = None
```

`Place.from_dict` içinde, `return cls(` öncesine:

```python
        evidence = d.get("importance_evidence")
        transport = d.get("transport")
```

ve `volatile=...` satırından sonra:

```python
            importance=d.get("importance"),
            importance_evidence=ImportanceEvidence.from_dict(evidence) if evidence is not None else None,
            highlights=[Highlight.from_dict(h) for h in d.get("highlights", [])],
            transport=Transport.from_dict(transport) if transport is not None else None,
```

- [ ] **Step 5: `museumdb/importance.py`**

```python
from __future__ import annotations

from museumdb.models import ImportanceEvidence

MUST_BLOG_MENTIONS = 4
MUST_REVIEW_COUNT = 20000
RECOMMENDED_BLOG_MENTIONS = 2
RECOMMENDED_REVIEW_COUNT = 3000


def classify(evidence: ImportanceEvidence | None) -> str | None:
    if evidence is None or (evidence.blog_mentions is None and evidence.review_count is None):
        return None
    blogs = evidence.blog_mentions or 0
    reviews = evidence.review_count or 0
    if blogs >= MUST_BLOG_MENTIONS or reviews >= MUST_REVIEW_COUNT:
        return "must"
    if blogs >= RECOMMENDED_BLOG_MENTIONS or reviews >= RECOMMENDED_REVIEW_COUNT:
        return "recommended"
    return "optional"
```

- [ ] **Step 6: `museumdb/schema.json`**

`$defs` içine (`"slug"` tanımından sonra) ekle:

```json
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
    "count": {"type": ["integer", "null"], "minimum": 0},
    "importance_evidence": {
      "type": "object",
      "required": ["checked"],
      "additionalProperties": false,
      "properties": {
        "blog_mentions": {"$ref": "#/$defs/count"},
        "review_count": {"$ref": "#/$defs/count"},
        "review_source": {"enum": ["google", "tripadvisor", null]},
        "urls": {"type": "array", "items": {"type": "string"}},
        "checked": {"$ref": "#/$defs/date"}
      }
    },
    "highlight": {
      "type": "object",
      "required": ["name"],
      "additionalProperties": false,
      "properties": {
        "name": {"type": "string", "minLength": 1},
        "coords": {"$ref": "#/$defs/coords"}
      }
    },
    "transport": {
      "type": "object",
      "required": ["checked"],
      "additionalProperties": false,
      "properties": {
        "mode": {"type": ["string", "null"]},
        "departure": {"type": ["string", "null"]},
        "one_way_min": {"$ref": "#/$defs/count"},
        "last_return": {"type": ["string", "null"], "pattern": "^[0-9]{2}:[0-9]{2}$"},
        "source": {"anyOf": [{"$ref": "#/$defs/source"}, {"type": "null"}]},
        "url": {"type": ["string", "null"]},
        "checked": {"$ref": "#/$defs/date"}
      }
    },
```

`place` içindeki satır içi `"coords": { "oneOf": [...] }` bloğunun tamamını `"coords": {"$ref": "#/$defs/coords"},` ile değiştir. `place.properties` sonuna (`"volatile"`'dan sonra) ekle:

```json
        ,
        "importance": {"enum": ["must", "recommended", "optional", null]},
        "importance_evidence": {"anyOf": [{"type": "null"}, {"$ref": "#/$defs/importance_evidence"}]},
        "highlights": {"type": "array", "items": {"$ref": "#/$defs/highlight"}},
        "transport": {"anyOf": [{"type": "null"}, {"$ref": "#/$defs/transport"}]}
```

(Baştaki virgül, `volatile` nesnesinin kapanış `}`'ından hemen sonra gelir; JSON'un geçerli olduğunu `python3 -m json.tool museumdb/schema.json > /dev/null` ile doğrula.)

- [ ] **Step 7: `museumdb/validation.py`**

`validate_city_dict`'in sonuna (çift id kontrolünden sonra):

```python
    for field_name, allowed_type in (("highlights", "district"), ("transport", "daytrip")):
        misplaced = [p["id"] for p in data["places"] if p.get(field_name) and p["type"] != allowed_type]
        if misplaced:
            raise ValidationError(
                f"{field_name} is only allowed on {allowed_type} places: {', '.join(misplaced)}"
            )
```

- [ ] **Step 8: `museumdb/merge.py`**

- Import ekle: `from museumdb.importance import classify`
- `merge_city` içinde, `synthesize` döngüsünü şöyle genişlet:

```python
    for place in result.places:
        if place.duration is not None:
            place.duration = synthesize(place.duration.signals, place.duration.notes)
        place.importance = classify(place.importance_evidence)
```

- `_merge_place` içinde `_merge_fields(current.volatile, incoming.volatile)` satırından sonra:

```python
    if incoming.importance_evidence is not None:
        current.importance_evidence = copy.deepcopy(incoming.importance_evidence)
    if incoming.highlights:
        current.highlights = copy.deepcopy(incoming.highlights)
    if incoming.transport is not None:
        current.transport = copy.deepcopy(incoming.transport)
```

- [ ] **Step 9: Run all tests**

Run: `.venv/bin/pytest -q`
Expected: tümü PASS.

- [ ] **Step 10: Commit**

```bash
git add museumdb tests
git commit -m "feat: place importance from evidence, district highlights, daytrip transport"
```

---

### Task 4: `migrate` komutu ve diskteki verinin yükseltilmesi

**Files:**
- Modify: `museumdb/store.py`, `museumdb/cli.py`, `tests/test_store.py`, `tests/test_cli.py`, `README.md`
- Modify (CLI ile): `data/cities/istanbul.json`, `data/cities/rome.json`, `data/index.json`

**Interfaces:**
- Consumes: `migrate.upgrade`, `migrate.upgrade_index_entry`, `parse_city`, `SCHEMA_VERSION` (Task 2–3)
- Produces:
  - `JsonStore.migrate_files() -> list[str]` — yükseltilen şehir slug'ları, alfabetik
  - CLI: `migrate` → stdout `{"migrated": ["istanbul", "rome"]}`, çıkış 0

- [ ] **Step 1: Write the failing tests**

`tests/test_store.py` sonuna:

```python
def write_v1(tmp_path, d):
    path = tmp_path / "cities" / f"{d['city']['slug']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(d), encoding="utf-8")
    return path


def test_migrate_rewrites_v1_files_and_index(tmp_path, rome_v1_dict, rome_dict):
    path = write_v1(tmp_path, rome_v1_dict)
    (tmp_path / "index.json").write_text(json.dumps([
        {"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220", "queried_at": "2026-10-01",
         "museum_count": 2}]), encoding="utf-8")
    store = make_store(tmp_path)
    assert store.migrate_files() == ["rome"]
    assert json.loads(path.read_text(encoding="utf-8")) == rome_dict
    index = json.loads((tmp_path / "index.json").read_text(encoding="utf-8"))
    assert index == [{"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220",
                      "queried_at": "2026-10-01", "place_count": 2}]


def test_migrate_is_idempotent(tmp_path, rome_v1_dict):
    path = write_v1(tmp_path, rome_v1_dict)
    store = make_store(tmp_path)
    store.migrate_files()
    before = path.stat().st_mtime_ns
    assert store.migrate_files() == []
    assert path.stat().st_mtime_ns == before


def test_migrate_empty_root(tmp_path):
    assert make_store(tmp_path).migrate_files() == []


def test_migrate_stops_on_invalid_file(tmp_path, rome_v1_dict):
    rome_v1_dict["museums"][0]["duration"]["signals"][0]["source"] = "yelp"
    path = write_v1(tmp_path, rome_v1_dict)
    before = path.read_text(encoding="utf-8")
    with pytest.raises(ValidationError, match="yelp"):
        make_store(tmp_path).migrate_files()
    assert path.read_text(encoding="utf-8") == before


def test_list_cities_reads_old_index(tmp_path):
    (tmp_path / "index.json").write_text(json.dumps([
        {"slug": "rome", "name": "Rome", "country": "IT", "wikidata_id": "Q220", "queried_at": "2026-10-01",
         "museum_count": 12}]), encoding="utf-8")
    assert make_store(tmp_path).list_cities() == [CityIndexEntry("rome", "Rome", "IT", "Q220", "2026-10-01", 12)]
```

`tests/test_cli.py` sonuna:

```python
def test_migrate_command(run, tmp_path, rome_v1_dict):
    path = tmp_path / "cities" / "rome.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(rome_v1_dict), encoding="utf-8")
    code, out, _ = run("migrate")
    assert code == 0 and json.loads(out) == {"migrated": ["rome"]}
    code, out, _ = run("migrate")
    assert code == 0 and json.loads(out) == {"migrated": []}
```

(`run` fixture'ı `--root` olarak aynı `tmp_path`'i kullanır.)

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv/bin/pytest tests/test_store.py tests/test_cli.py -q`
Expected: FAIL — `AttributeError: 'JsonStore' object has no attribute 'migrate_files'`, CLI `invalid choice: 'migrate'`.

- [ ] **Step 3: `museumdb/store.py`**

Import satırını genişlet: `from museumdb.models import PLANNING_FIELDS, SCHEMA_VERSION, VOLATILE_FIELDS, City, CityIndexEntry`

`list_cities`'ten sonra:

```python
    def migrate_files(self) -> list[str]:
        cities_dir = self.root / "cities"
        if not cities_dir.exists():
            return []
        migrated = []
        for path in sorted(cities_dir.glob("*.json")):
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
            except json.JSONDecodeError as e:
                raise ValidationError(f"{path}: invalid JSON: {e}") from e
            if isinstance(data, dict) and data.get("schema_version") == SCHEMA_VERSION:
                continue
            city = parse_city(data)
            _atomic_write_json(path, city.to_dict())
            self._update_index(city)
            migrated.append(city.slug)
        if migrated or self._index_has_old_entries():
            _atomic_write_json(self._index_path, [asdict(e) for e in self.list_cities()])
        return migrated

    def _index_has_old_entries(self) -> bool:
        if not self._index_path.exists():
            return False
        return any("museum_count" in e for e in json.loads(self._index_path.read_text(encoding="utf-8")))
```

- [ ] **Step 4: `museumdb/cli.py`**

`_parser` içinde `serve` tanımından önce:

```python
    sub.add_parser("migrate", help="upgrade every stored city file to the current schema")
```

`_resolve`'dan önce:

```python
def _migrate(store: JsonStore, args: argparse.Namespace) -> int:
    _print_json({"migrated": store.migrate_files()})
    return EXIT_OK
```

`_COMMANDS` sözlüğüne `"migrate": _migrate,` ekle.

- [ ] **Step 5: Run all tests**

Run: `.venv/bin/pytest -q`
Expected: tümü PASS.

- [ ] **Step 6: Gerçek veriyi yükselt**

```bash
.venv/bin/python -m museumdb.cli migrate
```

Expected: `{"migrated": ["istanbul", "rome"]}`. Sonra:

```bash
.venv/bin/python -m museumdb.cli table istanbul | head -3
python3 -c "import json; d=json.load(open('data/cities/istanbul.json')); print(d['schema_version'], len(d['places']), {p['type'] for p in d['places']})"
cat data/index.json
```

Expected: tablo ilk satırı `Istanbul — 15 müze (...)`; `2 15 {'museum'}`; index'te `place_count`, `museum_count` yok. `git diff --stat data/` yalnızca bu üç dosyayı göstermeli.

- [ ] **Step 7: README**

`README.md` CLI tablosunda `serve` satırından sonra ekle:

```markdown
| `migrate` | Diskteki tüm şehir dosyalarını güncel şemaya yükseltir (v1 `museums` → v2 `places`) |
```

ve "Kurallar:" paragrafının sonuna: `Şema v2: her kayıt bir **Yer** (\`places\`), müzeler \`type: "museum"\`; sözlük için [CONTEXT.md](CONTEXT.md).`

- [ ] **Step 8: Commit**

```bash
git add museumdb tests README.md data/cities/istanbul.json data/cities/rome.json data/index.json
git commit -m "feat: migrate command; data upgraded to schema v2"
```

---

### Task 5: `/muze` skill'ini v2'ye ve Önem kanıtına uyarlama

**Files:**
- Modify: `.claude/skills/muze/SKILL.md`, `tests/test_skill_doc.py`

**Interfaces:**
- Consumes: şema v2 (`places`, `type`, `importance_evidence`), `classify` eşikleri (Task 3), CLI `place_id` çıktısı (Task 2)
- Produces: `/muze`'nin ürettiği taslaklar v2 ve her müzede `importance_evidence` taşır.

- [ ] **Step 1: Write the failing test**

`tests/test_skill_doc.py` sonuna:

```python
def test_skill_draft_example_is_v2_with_importance_evidence():
    text = SKILL.read_text(encoding="utf-8")
    match = re.search(r"## Taslak örneği.*?```json\n(.*?)```", text, re.S)
    data = json.loads(match.group(1))
    assert data["schema_version"] == 2 and "places" in data
    place = data["places"][0]
    assert place["type"] == "museum"
    assert place["importance_evidence"]["blog_mentions"] is not None
    assert "importance" not in place


def test_skill_never_mentions_old_keys():
    text = SKILL.read_text(encoding="utf-8")
    assert "museums/" not in text and "museum_id" not in text
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv/bin/pytest tests/test_skill_doc.py -v`
Expected: `test_skill_draft_example_is_v2_with_importance_evidence` FAIL (`schema_version` 1), `test_skill_never_mentions_old_keys` FAIL (`museums/3/coords`).

- [ ] **Step 3: SKILL.md düzenlemeleri**

**Kurallar** bölümünde `- \`typical_min_h\`, ... alanlarını yazma; \`save\` bunları sinyallerden hesaplar.` satırından sonra ekle:

```markdown
- `importance` yazma; `save` onu `importance_evidence`'tan hesaplar (`must` / `recommended` / `optional`).
- Her müzenin `type` alanı `"museum"`; `scaffold` bunu koyar, değiştirme.
```

**Adım 2**'nin 2. maddesinden sonra yeni madde (sonraki maddelerin numarasını bir artır):

```markdown
3. Önem kanıtı için 2. maddedeki aramaların sonuç sayfalarını say: her müze kaç **farklı** blog / "top museums" listesinde geçiyor → `importance_evidence.blog_mentions`, sayılan sayfaların adresleri → `urls`. Aynı sitenin iki sayfası tek sayılır.
```

**Adım 3**'ün 4. maddesinden sonra yeni madde (5. madde 6 olur):

```markdown
5. Yorum sayısı: arama özetinde Google Maps yorum sayısı görünüyorsa onu, yoksa TripAdvisor'unkini al → `importance_evidence.review_count` (tam sayı, ör. "48,213 reviews" → `48213`) ve `review_source` (`google` / `tripadvisor`). Bulamazsan `review_count: null`, `review_source: null`. `checked` bugün.
```

**Ajan istem şablonundaki** dönüş satırını:

```
{"id", "category", "duration": {"signals": [...], "notes": [...]} | null,
 "planning": {"busiest", "queue_min", "advance_ticket"}, "volatile": {"price", "hours"}}
```

şununla değiştir:

```
{"id", "category", "duration": {"signals": [...], "notes": [...]} | null,
 "planning": {"busiest", "queue_min", "advance_ticket"}, "volatile": {"price", "hours"},
 "importance_evidence": {"review_count", "review_source", "checked"}}
```

ve şablonda `Her müze için: .claude/skills/muze/SKILL.md Adım 3 ve Adım 4'ü uygula` cümlesini değiştirme (Adım 3'teki yeni 5. madde böylece ajana da geçer). Ana oturum, ajandan gelen `review_count`'u Adım 2'de saydığı `blog_mentions` ve `urls` ile aynı `importance_evidence` nesnesinde birleştirir — bunu "Dönen sonuçları kaydetmeden önce denetle" listesine madde olarak ekle:

```markdown
  - `importance_evidence`: ajanın `review_count` / `review_source` değerini Adım 2'de saydığın `blog_mentions` ve `urls` ile tek nesnede birleştir.
```

**Adım 5**'te `(ör. \`museums/3/coords\`)` → `(ör. \`places/3/coords\`)`.

**Taslak örneği**'nde:
- `"schema_version": 1,` → `"schema_version": 2,`
- `"museums": [` → `"places": [`
- `"name": "Vatican Museums",` satırından sonra `"type": "museum",`
- `"user_notes": [],` satırından sonra:

```json
      "importance_evidence": {
        "blog_mentions": 6,
        "review_count": 98000,
        "review_source": "google",
        "urls": ["https://www.timeout.com/rome/museums/best-museums-in-rome"],
        "checked": "2026-10-01"
      },
```

Son olarak `grep -n "museums/\|museum_id\|schema_version.: 1" .claude/skills/muze/SKILL.md` boş dönmeli.

- [ ] **Step 4: Run all tests**

Run: `.venv/bin/pytest -q`
Expected: tümü PASS.

- [ ] **Step 5: Commit**

```bash
git add .claude/skills/muze/SKILL.md tests/test_skill_doc.py
git commit -m "docs(muze): schema v2 drafts with importance evidence"
```

---

## Sonraki planlar

Bu plan spec'teki uygulama adımları 1–2'yi kapsar. Kalanlar, her biri ayrı bir `docs/superpowers/plans/` dosyası olarak, bir öncekinin bitmesinden sonra yazılır:

- **Plan 2** — `/yer` skill'i, türe göre tablo/web görünümü, Önem eşiklerinin İstanbul verisiyle kalibrasyonu
- **Plan 3** — `restaurants` + `dishes` dizileri, `/restoran` skill'i
- **Plan 4** — `activities` dizisi, `/aktivite` skill'i, konaklama erişim denemesi
- **Plan 5** — rota CLI'ı: `route`, `route --verify`, `mapslink`, `nearby`, `plan-days`, `coverage`
- **Plan 6** — `/gezi` skill'i
