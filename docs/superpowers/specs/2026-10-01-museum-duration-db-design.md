# Müze Süre Veritabanı — Tasarım

Tarih: 2026-10-01
Durum: Taslak (kullanıcı onayı bekliyor)

## 1. Amaç

Bir şehir adı verildiğinde, o şehrin en popüler müzelerinde insanların ne kadar
süre geçirdiğini internetteki kullanıcı verilerinden (yorumlar, Google/TripAdvisor
süre özetleri) çıkarmak ve sonucu kalıcı olarak kaydetmek. Sorgulanan her şehir
veritabanına eklenir; zamanla dünyadaki müzeleri kapsayan bir veri birikir.

- **Kullanıcı:** Önce kendi gezi planlaması için kullanacak; ileride travelkardi
  ürününe dönüşebilir. Bu yüzden veri modeli ürün kalitesinde olmalı ve her
  değerin kaynağı (lisans takibi için) saklanmalı.
- **Arayüz:** Claude Code içinde `/muze <şehir> [--yenile]` komutu. Web araştırmasını
  Claude yapar; ek API anahtarı yok.
- **Depolama:** Şimdilik dosya (JSON). Gerçek veritabanına geçiş tek bir modülü
  değiştirerek yapılabilmeli.

### Başarı ölçütleri
- `/muze Rome` ilk çalıştırmada 10–15 müzeyi süre aralığı, güven seviyesi,
  kaynaklar ve bağlam notlarıyla kaydeder ve tablo olarak gösterir.
- Aynı şehir tekrar sorulduğunda web araştırması yapılmadan kayıt gösterilir;
  yalnızca 90 günden eski sık değişen alanlar tazelenir.
- Hiçbir değer kaynaksız kaydedilmez; bulunamayan değer `null` kalır.
- Depolama arayüzü, skill'e dokunmadan başka bir backend ile değiştirilebilir.

## 2. Kaynak stratejisi (Katmanlı hibrit)

| Veri | Birincil kaynak | Destek / yedek |
|---|---|---|
| Müze listesi, kimlik, koordinat, resmi site, kategori | Wikidata (SPARQL) | OpenStreetMap |
| Popülerlik sırası | Web araması ("top museums in <city>") | Wikidata site bağlantı sayısı |
| Süre | Google "people typically spend" ve TripAdvisor "suggested duration" (arama sonucu özetlerinden) | Reddit, TripAdvisor yorum parçaları, bloglar |
| Bağlam notları, kalabalık saatler, kuyruk | Reddit, yorumlar, bloglar | Google kalabalık bilgisi (özetten) |
| Fiyat, açılış saatleri, önceden bilet | Resmi site | Wikidata/OSM `opening_hours` |

Notlar:
- Google Places API süre alanını vermez; TripAdvisor ve Google sayfaları doğrudan
  kazınmaz. Süre değerleri arama sonucu özetlerinden okunur.
- Bir kaynak erişimi engellerse arama özetiyle yetinilir.
- Kaynakların gerçekte ne verdiği ilk uygulama adımında Roma ile denenir ve
  bulgular bu belgeye (Bölüm 9) eklenir.

## 3. Veri modeli

### Dosya düzeni
```
data/
  cities/<slug>.json   # şehir başına bir dosya, slug İngilizce (ör. rome)
  index.json           # [{slug, name, country, wikidata_id, queried_at, museum_count}]
```

### Şehir dosyası
```json
{
  "schema_version": 1,
  "city": { "name": "Rome", "country": "IT", "wikidata_id": "Q220", "queried_at": "2026-10-01" },
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
        "typical_min_h": 3, "typical_max_h": 4,
        "fast_h": 2, "thorough_h": 6,
        "confidence": "high",
        "notes": ["Sesli rehberle +1 saat"],
        "signals": [
          { "source": "google", "value": "3–4 h", "url": null, "checked": "2026-10-01" },
          { "source": "tripadvisor", "value": "More than 3 hours", "url": null, "checked": "2026-10-01" },
          { "source": "reddit", "value": "~5 h with audio guide", "url": "https://…", "checked": "2026-10-01" }
        ]
      },

      "planning": {
        "busiest":        { "value": "Sa–Ça 10:00–13:00", "source": "google", "checked": "2026-10-01" },
        "queue_min":      { "value": "60–120", "source": "reddit", "checked": "2026-10-01" },
        "advance_ticket": { "value": "strongly_recommended", "source": "official", "checked": "2026-10-01" }
      },
      "volatile": {
        "price": { "value": "€20 adult", "source": "official", "checked": "2026-10-01" },
        "hours": { "value": "Mo–Sa 08:00–19:00", "source": "official", "checked": "2026-10-01" }
      }
    }
  ]
}
```

### Kurallar
- **Kimlik:** Wikidata ID; yoksa `osm:<type>/<id>`; o da yoksa `slug:<city>/<museum-slug>`.
- **Süre iki katmanlı:** `signals` ham değerler, diğer alanlar türetilmiş özet.
  Özet her zaman `signals`'tan yeniden hesaplanabilir (`synth.py`).
- **Güven seviyesi:**
  - `high`: en az 2 kaynağın aralıkları örtüşüyor.
  - `medium`: tek güçlü kaynak (`google` veya `tripadvisor`), ya da güçlü kaynaklar örtüşmüyor.
  - `low`: yalnızca `reddit` / `blog` sinyalleri.
  - Sinyal yoksa `duration: null`.
- **Kaynak listesi (sabit):** `google`, `tripadvisor`, `reddit`, `blog`, `official`, `wikidata`, `osm`.
- **Bayatlama:** `planning` ve `volatile` altındaki her alanın kendi `checked` tarihi
  var; 90 günden eskiyse bayat sayılır. `duration` yalnızca `--yenile` ile güncellenir.
- **Kullanıcı notları:** `user_notes` elle eklenir; birleştirmede asla ezilmez.
- **Kayıp değer:** Bulunamayan alan `{"value": null, "source": null, "checked": <tarih>}` olarak tutulur
  (böylece "bakıldı ama bulunamadı" ile "hiç bakılmadı" ayırt edilir).
- **Sürüm:** `schema_version` ile ileride migration betikleri.

### Veritabanı eşlemesi (ileride)
`cities`, `museums`, `duration_signals(museum_id, source, value, url, checked)`,
`field_values(museum_id, field, value, source, checked)`.

## 4. Komut akışı: `/muze <şehir> [--yenile]`

Skill: `.claude/skills/muze/SKILL.md`. Web araştırmasını Claude yapar; dosya
işlemleri `museumdb` CLI'ı üzerinden yapılır.

0. **Şehri çözümle:** Ad Wikidata'da aranıp kimliğe eşlenir; slug İngilizce.
   Birden çok aday varsa kullanıcıya sorulur.
1. **Önbellek:** `cli get <slug>`.
   - Kayıt var ve `--yenile` yok → `cli stale <slug>` ile bayat alanlar alınır,
     yalnızca onlar webden tazelenir → Adım 5.
   - Kayıt yok veya `--yenile` → Adım 2–5.
2. **Müze listesi:** Wikidata SPARQL ile şehirdeki müzeler; web aramasıyla
   popülerlik sırası; ilk 10–15 seçilir; temel bilgiler Wikidata'dan.
3. **Süre sinyalleri (müze başına):** "<müze> how long to spend" aramaları;
   Google/TripAdvisor süre özetleri; 2–3 Reddit/yorum/blog parçasından bağlam
   notları, kalabalık saatler, kuyruk.
4. **Resmi site:** fiyat, saatler, önceden bilet. Okunamazsa `null`; uydurma yok.
5. **Kaydet:** Taslak JSON `cli save <slug>`'a verilir; modül doğrular, özeti
   hesaplar, mevcut kayıtla birleştirir, atomik yazar, `index.json`'u günceller.
6. **Göster:** `cli table <slug>` çıktısı sohbette gösterilir:
   ```
   Rome — 12 müze (8 yüksek, 3 orta, 1 düşük güven)
   Müze                Süre      Hızlı/Detaylı  Not
   Vatican Museums     3–4 sa    2 / 6 sa       Bilet önceden şart
   ```

### Hata durumları
- Süre sinyali yok → müze kaydedilir, `duration: null`, tabloda "veri yok".
- Kaynak engelli → arama özetiyle devam.
- Doğrulama hatası → kayıt yazılmaz, hata gösterilir, eski dosya bozulmaz.
- Yarıda kesilme → atomik yazma sayesinde eski dosya sağlam kalır.

## 5. Kod yapısı

```
travelkardi/
  .claude/skills/muze/SKILL.md
  museumdb/
    __init__.py
    models.py    # dataclass: City, Museum, Duration, Signal, FieldValue
    schema.json  # JSON Schema
    store.py     # Store protokolü + JsonStore
    synth.py     # signals → özet + güven (saf fonksiyonlar)
    cli.py       # get / stale / save / table
  data/
  tests/
```

### Depolama arayüzü
```python
class Store(Protocol):
    def get_city(self, slug: str) -> City | None: ...
    def save_city(self, city: City) -> None: ...          # doğrula + birleştir + atomik yaz
    def stale_fields(self, slug: str, max_age_days: int = 90) -> list[tuple[str, str]]: ...
                                                          # [(museum_id, "volatile.price"), ...]
    def list_cities(self) -> list[CityIndexEntry]: ...
```
Bugün `JsonStore`; ileride `SqliteStore` / `PostgresStore` aynı arayüzle.

### CLI
```
python -m museumdb.cli get <slug>           # kayıt JSON, yoksa çıkış kodu 1
python -m museumdb.cli stale <slug>         # bayat alanlar (JSON)
python -m museumdb.cli save <slug> < draft.json
python -m museumdb.cli table <slug>
```
Python tarafı ağa çıkmaz; deterministik ve test edilebilir. İleride bağımsız bir
toplayıcı (Claude API ile) bu modülü aynen kullanabilir.

### Bağımlılıklar
Python 3.11+, `jsonschema`, `pytest`. Başka bağımlılık yok.

## 6. Birleştirme kuralları (`save_city`)
- Müzeler `id` ile eşlenir.
- Gelen alan değeri `null` değilse veya mevcut değer yoksa yazılır; gelen `null`
  mevcut dolu değeri ezmez (yalnızca `checked` güncellenir).
- `signals`: aynı `source` için yeni sinyal eskisinin yerini alır; farklı
  kaynaklar korunur. Özet yeniden hesaplanır.
- `user_notes` asla değiştirilmez.

## 7. Testler (pytest, TDD)
- `synth`: süre metni ayrıştırma ("3–4 h", "More than 3 hours", "1-2 hours",
  "~5 h", "90 min"); aralık hesaplama; güven kuralları; sinyal yoksa `None`.
- `store`: kaydet/oku turu; birleştirme kuralları (Bölüm 6); 90 gün bayatlama;
  şemaya uymayan taslağın reddi; yazma hatasında eski dosyanın korunması;
  `index.json` güncellemesi.
- `cli`: dört komutun uçtan uca çalışması (geçici dizinde).
- Web toplama otomatik test edilmez; Roma ile manuel deneme yapılır.

## 8. Kapsam dışı
Web arayüzü, zamanlanmış toplu tarama, gerçek veritabanı, çoklu dil
(adlar İngilizce + yerel; notlar Türkçe), şehir başına 15'ten fazla müze.

## 9. Kaynak deneme bulguları
Roma denemesinden sonra doldurulacak: her kaynak için erişilebilirlik, hangi
alanları verdiği, güvenilirlik gözlemleri.
