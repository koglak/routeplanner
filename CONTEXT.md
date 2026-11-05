# travelkardi

Bir şehri gezmek için, kullanıcının tarzına uyan gün gün gezi planları hazırlayan sistemin dili. Planlar yerel veritabanındaki Yer kayıtlarından beslenir.

## Language

**Yer**:
Plana girebilen, koordinatı olan gezilecek nokta. Müze, Yer'in bir türüdür.
_Avoid_: mekan, attraction, POI

**Önem**:
Bir Yer'in mutlaka / önerilir / opsiyonel derecesi. Bloglarda geçme sıklığı ve haritadaki yorum sayısından çıkarılır. "Mutlaka" olan bir Yer, türü normalde Uğrak olsa bile içine girilen ziyaret olur. Kullanıcının planlamadaki değişikliği yalnızca o planda kalır.

**Günübirlik**:
Ana şehirden gidip aynı gün dönülen, şehir dışındaki Yer türü (ör. Büyükada, Tivoli). Ana şehrin kaydında, ulaşım şekli ve gidiş süresiyle tutulur; planda yarım ya da tam gün alır. Gece kalınan şehir değişmez — bu ülke planından farklıdır.

**Müze**:
Türü müze olan Yer. Kendine özgü süre ve kalabalık bilgisi taşır.

**Gezgin Profili**:
Kullanıcının gezme tarzını tarif eden, planlamanın uyduğu kurallar dosyası.
_Avoid_: tercih, ayar

**Gezi Planı**:
Bir şehir için hazırlanmış, günlere bölünmüş program. Repoda kalıcı bir dosya olarak saklanır ve sonradan güncellenebilir; bir şehrin birden çok planı olabilir.
_Avoid_: itinerary, rota

**Yürüyüş Turu**:
Bir Gün Planı'nın içindeki, birden çok noktayı yürüyerek bağlayan sıralı güzergah bloğu.

**Uğrak**:
Bir Yer'in plandaki rolü: ayrı ziyaret değil, Yürüyüş Turu üzerinde kısa duruş (dışarıdan görme, fotoğraf). Cami, kilise, meydan, anıt gibi türlerde varsayılandır; tarihî önemi çok yüksek Yer'ler (ör. Ayasofya) istisnadır. Rol Yer'e değil plana aittir.
_Avoid_: geçiş noktası

**Semt**:
Tek nokta değil bölge olan Yer türü; içindeki önemli noktaları listeler ve planda Yürüyüş Turu olarak açılır.

**Hızlı Süre / Detaylı Süre**:
Bir Müze için iki ziyaret süresi. Plan varsayılan olarak Hızlı Süre'yi kullanır; kullanıcı müze bazında Detaylı Süre'yi seçebilir.

**Restoran**:
Bir şehirde popüler kaynaklarda öne çıkan, veritabanında saklanan yemek yeri. Plana öğün olarak girer, gezilecek nokta değildir.
_Avoid_: yemek yeri, mekan

**Geleneksel Yemek**:
Bir şehre ya da bölgeye özgü yemek. Onu iyi yapan Restoran'larla ilişkilidir; sokak yemeği gibi hiçbir Restoran'a bağlı olmayabilir.
_Avoid_: yöresel yemek, lokal yemek

**Aktivite**:
Bir yer değil, yapılan şey (Boğaz turu, hamam, balon). Tek bir firmanın ürünü değil, etkinliğin kendisidir: süre aralığı, fiyat aralığı, kalkış noktaları ve örnek ilanlarla veritabanında saklanır.
_Avoid_: tur, deneyim

**Önerilen Süre**:
Gün sayısını planın kendisinin hesapladığı mod: Önem'i mutlaka ve önerilir olan Yer'lerin hepsini sığdıran gün sayısı. Tarih içermez; günler sıra numarasıyla anılır, kapalı günler yalnızca uyarı olarak yazılır.

**Sabit Aralık**:
Tarihleri kullanıcının verdiği mod. Sığmayan Yer'ler planın sonunda listelenir.

**Kullanıcı Eklemesi**:
Kullanıcının planlama sırasında verdiği, veritabanında olmayan Yer. Yalnızca o Gezi Planı'nda yaşar, veritabanına yazılmaz. Planlamada canlı aramayla bulunan Restoran'lar da aynı şekilde planda kalır.

## Relationships

- Bir **Gezi Planı** tek bir şehre aittir ve bir **Gezgin Profili**'ne göre hazırlanır
- Bir **Gezi Planı** günlerden oluşur; bir gün **Yer** ziyaretleri ve **Yürüyüş Turu** blokları içerir
- Bir **Geleneksel Yemek** birden çok **Restoran**'la, bir **Restoran** birden çok **Geleneksel Yemek**'le ilişkili olabilir
- Bir **Gezi Planı** ya **Önerilen Süre** ya **Sabit Aralık** modundadır
- Plana normalde öğün saatinde bulunulan yerin yakınındaki **Restoran** girer; kullanıcının "mutlaka" dediği **Restoran** bir **Yer** gibi rotaya konur
- **Kullanıcı Eklemesi** bir **Gezi Planı**'na aittir, veritabanına değil

## Flagged ambiguities

- "rota" hem bir günün sıralı güzergahı hem de planın tamamı için kullanıldı — planın tamamı **Gezi Planı**, güzergah bloğu **Yürüyüş Turu**.
- "konaklama" — v1'de veritabanında yok; Booking/Airbnb gibi kaynaklara erişilemezse dışarıda kalır.
- "şehri/ülkeyi" — v1 yalnızca şehir; ülke planı v2.
