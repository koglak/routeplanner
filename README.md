# travelkardi — müze süreleri

Bir şehrin popüler müzelerinde insanların ne kadar süre geçirdiğini web'den toplayıp
kaynaklarıyla birlikte JSON olarak saklayan küçük bir veritabanı.

- **Araştırma**: Claude Code skill'i `/muze` (web araması, Google/Tripadvisor süre özetleri, Reddit, bloglar, resmî siteler).
- **Depolama**: `museumdb` Python paketi — doğrulama, birleştirme, süre/güven hesabı, atomik yazma.
- **Görüntüleme**: terminalde Türkçe özet tablo ya da yerel web arayüzü.

## Kurulum

Python 3.11+ gerekir.

```sh
python3 -m venv .venv
.venv/bin/pip install -e '.[dev]'
.venv/bin/pytest
```

## `/muze` skill'i

Claude Code içinde, repo kökünde:

```
/muze rome
/muze istanbul --yenile
```

Skill ([.claude/skills/muze/SKILL.md](.claude/skills/muze/SKILL.md)) şunları yapar:

1. Şehri `resolve` ile Wikidata'da bulur (birden çok aday varsa sorar); slug ve ülke kodu CLI'dan gelir.
2. `status` ile kayda bakar: tazeyse doğrudan tabloyu gösterir; yalnızca bayat alanlar (fiyat, saat, kalabalık…) varsa onları tazeler.
3. Yoksa `candidates` + web aramasıyla 10–15 popüler müzeyi seçer, `scaffold` ile kimlik alanları ve OSM saatleri dolu taslağı üretir.
4. Her müze için süre sinyallerini, kuyruk/kalabalık bilgisini ve resmî siteden fiyat/saat/bilet bilgisini toplayıp taslağa ekler.
5. Taslağı `save` ile kaydeder, sonra tabloyu gösterir.

Deterministik işler (Wikidata/OSM sorguları, koordinat çevirme, taslak iskeleti) CLI'da; Claude yalnızca
müze seçimi ve web araştırmasını yapar.

Kurallar: hiçbir değer kaynaksız yazılmaz, bulunamayan değer `null` kalır; `data/` altına yalnızca CLI ile yazılır.
`--yenile` olmadan `duration` alanına dokunulmaz.

## CLI

Hepsi repo kökünden: `.venv/bin/python -m museumdb.cli <komut>`. Veri dizini `--root` ya da `$MUSEUMDB_ROOT`, varsayılan `./data`.

| Komut | Ne yapar |
|---|---|
| `get <slug>` | Kayıtlı şehir JSON'u |
| `status <slug>` | `missing` / `fresh` / `stale` ve bayat alanlar |
| `stale <slug> [--max-age-days 90]` | Tazelenmesi gereken `planning`/`volatile` alanları |
| `save <slug> < taslak.json` | Taslağı doğrular, mevcut kayıtla birleştirir, kaydeder |
| `table <slug>` | Türkçe özet tablo |
| `serve [--host 127.0.0.1] [--port 8765]` | Yerel web arayüzü (salt okunur) |
| `resolve <şehir adı>` | Wikidata'da şehir adayları (slug + ülke kodu) |
| `candidates <şehir QID>` | Şehirdeki müzeler, Wikipedia sitelink sayısına göre |
| `lookup <müze adı>` | Wikidata'da müze arama |
| `scaffold <slug> <şehir QID> <müze QID>...` | Kimlik alanları dolu taslak iskeleti (OSM açılış saatleriyle) |

Çıkış kodları: `0` tamam, `1` kayıt yok, `2` geçersiz girdi, `3` ağ hatası. Hatalar stderr'e `error: …` olarak yazılır.

Örnek:

```
$ .venv/bin/python -m museumdb.cli table rome
Rome — 12 müze (6 yüksek, 2 orta, 4 düşük güven)
Müze                  Süre    Hızlı/Detaylı  Not
Vatican Museums       2–3 sa  2 / 3 sa       Tüm rota yaklaşık 7,5 km
Galleria Borghese     2–3 sa  2 / 3 sa       Bilet önceden şart
…
```

## Web arayüzü

```sh
.venv/bin/python -m museumdb.cli serve
# http://127.0.0.1:8765
```

Bağımlılıksız (stdlib `http.server`) salt okunur bir arayüz: şehir listesi ve arama, müzeleri kategoriye
göre filtreleme ve sıralama, müze ayrıntıları (süre sinyalleri ve kaynakları, bilet, saat, fiyat).
Henüz başlangıç aşamasında; düzenleme yok.

| Uç nokta | Döner |
|---|---|
| `GET /api/cities` | `data/index.json` girdileri |
| `GET /api/cities/<slug>` | Şehir JSON'u |
| `GET /` | [museumdb/web_static/](museumdb/web_static/) altındaki statik dosyalar |

## Veri modeli

```
data/
  index.json          # [{slug, name, country, wikidata_id, queried_at, museum_count}]
  cities/<slug>.json  # schema_version: 1 — museumdb/schema.json
```

- **Kimlik**: Wikidata QID; yoksa `osm:<tip>/<id>`; o da yoksa `slug:<şehir>/<müze>`.
- **Kaynaklar**: `google`, `tripadvisor`, `reddit`, `blog`, `official`, `wikidata`, `osm`.
- **Süre**: `duration.signals[]` kaynağın metnini birebir tutar; `typical_min_h`, `typical_max_h`, `fast_h`, `thorough_h`
  ve `confidence` kaydederken sinyallerden hesaplanır.
- **Güven**: `high` = en az iki kaynağın aralığı örtüşüyor; `medium` = tek güçlü kaynak (Google/Tripadvisor) ya da
  güçlü kaynaklar çelişiyor; `low` = yalnızca Reddit/blog.
- **Bayatlama**: `planning` ve `volatile` altındaki her alanın kendi `checked` tarihi var; 90 günden eskisi bayat.
- **Birleştirme**: gelen `null` dolu değeri ezmez, aynı kaynaklı sinyal yenisiyle değişir, `user_notes` hiç ezilmez.

## Kod düzeni

| Modül | Görev |
|---|---|
| `models.py` | Dataclass'lar |
| `validation.py` | JSON Schema doğrulama, slug kontrolü |
| `synth.py` | Sinyallerden süre aralığı ve güven |
| `merge.py` | Yeni taslağı mevcut kayıtla birleştirme |
| `store.py` | `Store` protokolü, `JsonStore` (atomik yazma, index, bayatlama) |
| `table.py` | Terminal tablosu |
| `wikidata.py` | Wikidata / OpenStreetMap sorguları |
| `scaffold.py` | Wikidata'dan taslak iskeleti |
| `web.py`, `web_static/` | Web arayüzü |
| `cli.py` | Komut satırı |

Tasarım ve uygulama planı: [docs/superpowers/plans/](docs/superpowers/plans/).
