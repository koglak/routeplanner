# Gezi Planlayıcı — Tasarım

Tarih: 2026-10-08
Durum: Taslak (kullanıcı onayı bekliyor)
Sözlük: [CONTEXT.md](../../../CONTEXT.md) · Karar: [ADR 0001](../../adr/0001-muzeden-yere-genelleme.md)

## 1. Amaç

Bir şehir için, kullanıcının **Gezgin Profili**'ne uyan, gün gün **Gezi Planı** hazırlamak. Planın
malzemesi (Yer, Restoran, Geleneksel Yemek, Aktivite) yerel veritabanından gelir; veritabanı her
kavram için ayrı bir araştırma skill'iyle doldurulur. Plan yazımı en son yazılan `/gezi` skill'idir.

### Kapsam
- v1: tek şehir, iki mod (**Önerilen Süre**, **Sabit Aralık**), yürüyüş rotası, öğün önerisi,
  toplam giriş ücreti + aktivite fiyat aralıkları.
- v2: ülke planı (şehir zinciri), tam bütçe (yemek/ulaşım/konaklama), konaklama (kaynaklara
  erişilemezse).

### Başarı ölçütleri
- `/gezi istanbul` (Önerilen Süre) DB'den kaç gün gerektiğini hesaplar ve tarihsiz, gün numaralı bir
  plan üretir; kapalı günler uyarı olarak yazılır.
- `/gezi istanbul 12-15 Kasım` (Sabit Aralık) kapalı günlere ziyaret koymaz; sığmayanları listeler.
- Her gün için sıralı durak listesi, yürüme süreleri ve Google Maps yürüyüş linki vardır.
- Plan `plans/` altına yazılır ve sonraki oturumda açılıp güncellenebilir.
- Hiçbir DB değeri kaynaksız yazılmaz (mevcut `museumdb` kuralı tüm kavramlara genişler).

## 2. Bileşenler

| Bileşen | Tür | Görev |
|---|---|---|
| `profil.md` | Dosya | Gezgin Profili: tempo ve tercih kuralları |
| `museumdb` → genelleşmiş CLI | Python | Şema, doğrulama, birleştirme, kayıt, rota hesabı |
| `/muze` | Skill (mevcut) | Müze türündeki Yer'leri araştırır — değişmez, yalnızca yeni şemaya yazar |
| `/yer` | Skill (yeni) | Müze dışı Yer türlerini araştırır |
| `/restoran` | Skill (yeni) | Restoran + Geleneksel Yemek ve aralarındaki ilişki |
| `/aktivite` | Skill (yeni) | Aktivite türlerini (GetYourGuide vb.) araştırır |
| `/gezi` | Skill (yeni, en son) | Planı kullanıcıyla birlikte hazırlar, `plans/`e yazar |

İlke `/muze`'dekiyle aynı: deterministik işler (sorgu, doğrulama, mesafe, sıralama, link) CLI'da;
Claude yalnızca seçim, web araştırması ve kullanıcıyla konuşmayı yapar. Araştırma skill'leri
paralel ajan kullanabilir (`/muze`'deki şablon); `/gezi` etkileşimlidir, ajana devredilmez.

## 3. Gezgin Profili (`profil.md`)

Repo kökünde, insan tarafından düzenlenen tek dosya. `/gezi` her çalıştırmada okur. Alanlar
(değerler ilk yazımda kullanıcıyla doldurulur):

- Günün başlangıç / bitiş saati
- Öğün saatleri (yerel kültüre göre kaydırma kuralıyla) ve restoran seçim ölçütü
- Müze süresi: varsayılan Hızlı Süre; Detaylı Süre müze bazında sorulur
- Uğrak sayılan Yer türleri (cami, kilise, sinagog, meydan, anıt, çeşme, köprü…)
- Toplu taşımaya geçiş eşiği (yürüme mesafesi)
- Günde en fazla müze sayısı
- Sevilen / sevilmeyen Yer türleri
- Sıralama kuralları (kalabalık yer açılışa, seyir noktası gün batımına…)

## 4. Veri modeli (schema_version 2)

Şehir başına tek dosya korunur: `data/cities/<slug>.json`. `museums` dizisi `places` olur; mevcut
müze kayıtları `type: "museum"` ile taşınır (tek seferlik `migrate` komutu, v1 dosyaları okunurken
de otomatik yükseltilir).

```
{
  "schema_version": 2,
  "city": {...},
  "places": [Yer],
  "restaurants": [Restoran],
  "dishes": [Geleneksel Yemek],
  "activities": [Aktivite]
}
```

Ortak kurallar: her değer `{value, source, checked}` ya da kaynaklı sinyal listesi; bulunamayan
`null`; `checked` tarihi tutulur ama otomatik tazeleme yok, yalnızca `--yenile`.

**Yer** — `id`, `name`, `name_local`, `type` (museum, religious, square, monument, viewpoint,
bazaar, park, district, daytrip…), `coords`, `importance` (`must` / `recommended` / `optional`),
`importance_evidence` (blog geçme sayısı, harita yorum sayısı, kaynaklar), `duration`,
`volatile` (saat, fiyat), `planning` (kalabalık, kuyruk, önceden bilet).
- `museum`: mevcut süre yapısı (Hızlı/Detaylı Süre) aynen.
- `district` (Semt): `highlights` — içindeki önemli noktaların listesi (ad + koordinat).
- `daytrip` (Günübirlik): `transport` (şekil, kalkış noktası, gidiş süresi, son dönüş), planda
  yarım/tam gün.
- Uğrak varsayılanı türden gelir; `importance: must` olan Yer (ör. Ayasofya) içine girilen ziyaret
  olur.

**Restoran** — `id`, `name`, `coords`, `area` (semt), `price_level`, `rating` + `review_count`,
`known_for` (Geleneksel Yemek id listesi), `importance`, kaynaklar.

**Geleneksel Yemek** — `id`, `name`, `name_local`, `description`, `restaurants` (Restoran id listesi,
boş olabilir), `where_found` (ör. "sokak", "Eminönü"). İlişki iki yönlü tutulmaz: kaynak
`known_for`'dur, ters yön CLI'da hesaplanır.

**Aktivite** — `id`, `name`, `kind` (boat, hammam, balloon, class, show…), `duration_range_h`,
`price_range` (para birimiyle), `departure_points` (ad + koordinat), `schedule_note`,
`sample_listings` (URL + kaynak), `importance`.

## 5. CLI eklemeleri

Mevcut komutlar (`get`, `status`, `save`, `table`, `serve`, `resolve`, `candidates`, `lookup`,
`scaffold`) kavram parametresi alır (`--kind place|restaurant|dish|activity`, varsayılan `place`).
Yeni komutlar:

| Komut | Ne yapar |
|---|---|
| `migrate [<slug>]` | v1 → v2 şema yükseltmesi |
| `coverage <slug>` | Hangi kavramların dolu/eksik olduğunu söyler (`/gezi` eksik veri sorusu için) |
| `route <noktalar.json>` | Kuş uçuşu × 1,3 ile en yakın komşu + 2-opt sıralama; mesafe ve yürüme süresi |
| `route --verify` | Son rotayı OSRM/ORS ile ölçer; erişilemezse sonucu `estimated: true` işaretler |
| `mapslink <noktalar.json>` | Google Maps yürüyüş linki; 9 ara noktadan fazlaysa böler |
| `nearby <slug> <lat,lon> --kind restaurant --max-min 10` | Bir noktaya yakın kayıtlar |
| `plan-days <slug> --profile profil.md` | Önerilen Süre: must + recommended Yer'leri sığdıran gün sayısı |

Rota yürüme hızı ve eşikler `profil.md`'den gelir; CLI profili okumaz, değerleri parametre olarak alır.

## 6. Araştırma skill'leri

Hepsi `/muze` iskeletini izler: şehri `resolve` et → `status` → aday listesi (web + CLI) → taslak →
`save`. Önem değeri her skill'de aynı yöntemle çıkarılır: kaç farklı blogda geçtiği ve harita
yorum sayısı; ham sayılar `importance_evidence`'a, eşiği `save` uygular.

- `/yer`: "things to do in X", Google Maps/TripAdvisor top attractions, yerel turizm sitesi.
  Semt için `highlights`, Günübirlik için ulaşım araştırır.
- `/restoran`: popüler yemek blogları ve "best restaurants in X"; önce şehrin Geleneksel
  Yemek listesi, sonra her yemek için onu iyi yapan Restoran'lar.
- `/aktivite`: GetYourGuide, Viator ve benzerlerinde etkinlik türleri; tek ürün değil, türün
  süre/fiyat aralığı ve 2–3 örnek ilan.
- Konaklama: Booking/Hostelworld/Airbnb erişimi ilk uygulama adımında denenir; bulgu bu belgeye
  eklenir. Erişim yoksa v2.

## 7. `/gezi` akışı

1. Şehri çözümle; `coverage` ile eksik kavramları bul → "toplayayım mı?" (evet ise ilgili
   araştırma skill'ini çalıştır, yalnızca eksik olanları).
2. Mod belirle: tarih verildiyse Sabit Aralık, yoksa Önerilen Süre (`plan-days`).
3. Tek mesajda sun: Yer listesi (Önem'e göre gruplu), Aktiviteler, Detaylı Süre istenecek
   müzeler, sınırda kalan Uğrak/ziyaret kararları. Sor: seçimler, konaklama semti, varış/ayrılış
   saatleri, Kullanıcı Eklemeleri.
4. Planla: coğrafi kümeleme → günlere dağıtım (Günübirlik kendi gününü alır) → kapalı gün kontrolü
   (Sabit Aralık'ta engel, Önerilen Süre'de uyarı) → gün içi `route` → Uğrak'ları Yürüyüş Turu
   üzerine yerleştir → öğün saatinde `nearby` ile Restoran; yoksa canlı web araması (DB'ye yazılmaz)
   → `route --verify` + `mapslink`.
5. Planı yaz: gün tabloları, yemek önerileri (ilgili Geleneksel Yemek'le), notlar, sığmayanlar,
   toplam giriş ücreti + aktivite fiyat aralıkları, "mesafeler tahmini" uyarısı.
6. Kaydet: `plans/<slug>-<YYYY-MM-DD|onerilen>.md`. Mevcut bir plan istenirse açılır, yalnızca
   değişen günler yeniden yazılır.

Kullanıcı Eklemeleri ve plan içi Önem değişiklikleri yalnızca plan dosyasında yaşar.

## 8. Uygulama sırası

1. `profil.md` (kullanıcıyla değerler)
2. Şema v2 + `migrate` + kavram parametreli CLI; `/muze`'yi yeni şemaya uyarlama
3. `/yer`
4. `/restoran`
5. `/aktivite` (+ konaklama erişim denemesi)
6. Rota CLI'ı (`route`, `route --verify`, `mapslink`, `nearby`, `plan-days`, `coverage`)
7. `/gezi`

Her adım kendi testleriyle (`tests/`) ve `museumdb` kurallarıyla tamamlanır; web arayüzü yeni
kavramları gösterecek şekilde 2. adımda güncellenir.

## 9. Açık konular

- Önem eşikleri (kaç blog / kaç yorum = must) — ilk şehir (İstanbul) verisiyle kalibre edilir.
- OSRM genel sunucusu mu, ORS anahtarı mı — 6. adımda denenip karar verilir.
- `museumdb` paket adı genelleşmeden sonra yanıltıcı; yeniden adlandırma ayrı bir karar.
