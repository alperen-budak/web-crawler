# CHECK_1 — Checkpoint 1 Raporu: Core Crawler Engine

> **Proje:** Google in One Day — Python Edition  
> **Checkpoint:** 1 — Core Crawler Engine (UI yok, API yok)  
> **Tarih:** 21 Mart 2026

---

## Ne Yaptık?

Sıfırdan, **sadece Python standart kütüphanesi** kullanarak çalışan bir web crawler motoru inşa ettik. Hiçbir üçüncü parti paket yok. Bu motor bir URL alıyor, o sayfayı indiriyor, içindeki kelimeleri ve linkleri çıkarıyor, kelimeleri dosyaya indexliyor ve bulunan linkleri de aynı şekilde işlemek üzere kuyruğa atıyor. Tüm bunları **arka plan thread'inde**, **thread-safe** şekilde yapıyor.

---

## Kullanılan Teknolojiler ve Neden

| Teknoloji | Nereden Geliyor | Ne İşe Yarıyor |
|---|---|---|
| `urllib.request` | Python stdlib | Web sayfalarını HTTP GET ile indirmek |
| `html.parser.HTMLParser` | Python stdlib | HTML'den link ve kelime çıkarmak |
| `threading.Thread` | Python stdlib | Crawler'ı arka planda çalıştırmak |
| `threading.Lock` | Python stdlib | Birden fazla thread aynı veriye yazarken bozulma olmaması için |
| `queue.Queue` | Python stdlib | BFS kuyruğu + back pressure (kuyruk dolunca bekle) |
| `collections.Counter` | Python stdlib | Bir sayfadaki kelime frekanslarını saymak |
| `json` | Python stdlib | Veriyi `.data` dosyalarına JSON formatında yazmak/okumak |
| `Docker` | Container | Projemizi her ortamda aynı şekilde çalıştırmak için |

---

## Dosya Dosya Ne Yapıyor

### 1. `src/crawler/fetcher.py` — Sayfa İndirici

**Tek iş:** Bir URL al, HTTP isteği yap, HTML'i string olarak geri ver.

```
fetch_page("https://example.com")  →  ("<html>...</html>", 200)
```

**Nasıl çalışıyor:**
- `urllib.request.Request` ile bir istek nesnesi oluşturuyor (User-Agent header'ı ekliyor)
- `urllib.request.urlopen()` ile bağlantıyı açıyor, `timeout=10` saniye
- Gelen yanıtın `Content-Type`'ına bakıyor: sadece `text/html` ise içeriği okuyor
- Byte'ları UTF-8 ile decode edip string'e çeviriyor
- **Hata yönetimi:** 404, timeout, bağlantı reddi gibi tüm hataları yakalıyor. Asla exception fırlatmıyor — hep `(mesaj, kod)` tuple'ı dönüyor

---

### 2. `src/crawler/parser.py` — HTML Ayrıştırıcı

**Tek iş:** Bir HTML string'i al, içindeki linkleri ve kelimeleri çıkar.

```
parse_page("<html>...<a href='/about'>...<p>hello world</p>...</html>", "https://example.com")
→  (["https://example.com/about"], ["hello", "world"])
```

**Nasıl çalışıyor:**
- `HTMLParser` sınıfından `_PageParser` adında bir alt sınıf türetiliyor
- `handle_starttag()` → `<a href="...">` etiketlerini yakalıyor, linki çıkarıyor
- `handle_data()` → Etiketler arasındaki metin içeriği alıyor, regex ile kelimelere ayırıyor
- **Akıllı filtreleme:**
  - `<script>`, `<style>`, `<noscript>` içindeki metinler **atlanıyor** (indexlenmez)
  - `mailto:`, `javascript:`, `tel:` linkleri **filtreleniyor**
  - URL fragment'ları (`#section`) **temizleniyor**
  - Göreceli linkler (`/about`) → mutlak URL'ye çevriliyor (`https://example.com/about`)
  - 2 karakterden kısa kelimeler atlanıyor

---

### 3. `src/storage/visited_store.py` — Ziyaret Edilen URL Deposu

**Tek iş:** Hangi URL'lerin daha önce ziyaret edildiğini takip et. Aynı URL iki kez işlenmesin.

```python
store = VisitedStore()
store.add("https://example.com")    # → True  (yeni eklendi)
store.add("https://example.com")    # → False (zaten var)
store.contains("https://example.com")  # → True
```

**Nasıl çalışıyor:**
- Bellekte bir Python `set` tutuyor — O(1) arama hızı
- Her ekleme sonrası `data/visited_urls.data` dosyasına yazıyor (her satır bir URL)
- Başlatıldığında dosyadan eski URL'leri yüklüyor (persistence)
- **Thread safety:** Tüm okuma/yazma işlemleri `threading.Lock` ile korunuyor

---

### 4. `src/storage/file_store.py` — Kelime Index Deposu

**Tek iş:** Kelimeleri ilk harflerine göre dosyalara yaz. `"python"` → `p.data`, `"crawler"` → `c.data`

```python
store = FileStore()
store.write_word("python", "https://example.com", "https://origin.com", depth=1, freq=5)
# → data/storage/p.data dosyasına bir satır JSON eklenir
```

**Dosya formatı (JSON Lines):**
```json
{"word": "python", "url": "https://example.com", "origin": "https://origin.com", "depth": 1, "freq": 5}
{"word": "parser", "url": "https://other.com", "origin": "https://example.com", "depth": 2, "freq": 3}
```

**Nasıl çalışıyor:**
- Kelimenin ilk harfini alıyor → dosya adı (`a.data` ... `z.data`, rakamla başlayanlar `_.data`)
- `append` modunda açıyor → mevcut verilerin üzerine yazmıyor
- `write_words_batch()` ile toplu yazım desteği var (her sayfa için tek seferde yazıyor)
- **Thread safety:** Tüm dosya yazımları `threading.Lock` ile korunuyor

---

### 5. `src/crawler/queue_manager.py` — BFS Kuyruğu + Back Pressure

**Tek iş:** URL'leri sırayla işlemek için FIFO kuyruk. Kuyruk dolunca **durdur, bekle**.

```python
qm = QueueManager(maxsize=100)
qm.put(("https://example.com", 0))      # Kuyruğa ekle
url, depth = qm.get()                    # Kuyruktan al
```

**Back pressure nedir ve neden önemli:**
- Kuyruk `maxsize=100` ile sınırlı
- Kuyruk dolunca `put()` **bloklanıyor** — yeni URL ekleyen thread duruyor ve beklentiye geçiyor
- Bu sayede bellek patlaması önleniyor — crawler kendini kontrol ediyor
- `queue.Queue` zaten thread-safe, ek kilit gerekmez

---

### 6. `src/crawler/worker.py` — BFS Worker (Asıl İşi Yapan)

**Tek iş:** Kuyruktan URL al → indir → parse et → indexle → yeni linkleri kuyruğa at. Tekrarla.

**Adım adım akış (her URL için):**

```
1. Kuyruktan (url, depth) al
2. fetch_page(url) → HTML indir
3. parse_page(html) → linkler ve kelimeler çıkar
4. Counter(kelimeler) → her kelimenin frekansını say
5. file_store.write_words_batch() → kelimeleri dosyaya yaz
6. Her yeni link için:
   a. visited_store.add(link) → daha önce ziyaret edildi mi?
   b. Yeni ise: queue.put((link, depth+1)) → kuyruğa ekle
   c. Kuyruk doluysa: back pressure logu yaz, blokla ve bekle
7. Her adımı data/jobs/{id}.data dosyasına logla
8. Kuyruk boşalınca → status = "completed"
```

**Derinlik kontrolü:**
- `depth < max_depth` kontrolü yapılıyor
- depth=0 başlangıç URL'si, depth=1 onun linkleri, depth=2 onların linkleri...
- max_depth'e ulaşılınca yeni link eklenmez → tarama sınırlı kalır

**Rate limiting:**
- Her URL işlendikten sonra `time.sleep(rate)` ile beklenir
- Hedef siteyi aşırı yüklememek için (politeness)

---

### 7. `src/crawler/crawler.py` — Crawler Başlatıcı

**Tek iş:** Tüm parçaları bir araya getirip arka plan thread'inde crawler'ı başlat.

```python
crawler_id = start_crawl("https://example.com", depth=2)
# → "1774120068_140626653346616" (epoch_threadID)
```

**Başlatma akışı:**

```
1. VisitedStore oluştur (visited URL'leri yönetecek)
2. FileStore oluştur (kelime indexini yazacak)
3. QueueManager(maxsize=100) oluştur (BFS kuyruğu)
4. BFSWorker oluştur (tüm bileşenleri alıyor)
5. Seed URL'i visited'a ekle + kuyruğa koy
6. threading.Thread başlat → worker.run() çalışsın
7. crawler_id = "{epoch}_{thread.ident}" oluştur
8. crawler_id'yi hemen döndür (thread arka planda çalışmaya devam eder)
```

**Crawler ID formatı:** `1774120068_140626653346616`
- İlk kısım: Unix epoch (saniye cinsinden zaman damgası)
- İkinci kısım: Thread'in benzersiz kimliği
- Bu ikisi birlikte her job için benzersiz bir ID üretiyor

---

## Veri Akışı — Büyük Resim

```
start_crawl("https://example.com", depth=2)
    │
    ▼
┌─────────────────────────────────────────────┐
│            ARKA PLAN THREAD'İ               │
│                                             │
│  ┌───────────┐    BFS Kuyruğu              │
│  │ Queue     │◄── ("https://example.com",0) │
│  │ maxsize=  │                              │
│  │ 100       │    Back pressure:            │
│  └─────┬─────┘    Kuyruk dolunca bekle      │
│        │                                    │
│        ▼                                    │
│  ┌──────────────┐                           │
│  │ fetch_page() │  urllib.request            │
│  │ HTTP GET     │  → HTML string döner      │
│  └──────┬───────┘                           │
│         │                                   │
│         ▼                                   │
│  ┌──────────────┐                           │
│  │ parse_page() │  HTMLParser                │
│  │ Link + Word  │  → linkler, kelimeler     │
│  └──────┬───────┘                           │
│         │                                   │
│    ┌────┴────┐                              │
│    ▼         ▼                              │
│  Kelimeler  Linkler                         │
│    │         │                              │
│    ▼         ▼                              │
│  FileStore  VisitedStore                    │
│  p.data     visited_urls.data               │
│  e.data     + Kuyruğa geri ekle             │
│  ...        (depth+1 ile)                   │
└─────────────────────────────────────────────┘
```

---

## Thread Safety — Neyi Nasıl Koruyoruz

Birden fazla crawler aynı anda çalışabilir. Bu yüzden paylaşılan verilere eş zamanlı erişim **kilit (Lock)** ile korunuyor:

| Paylaşılan Veri | Koruma Mekanizması | Neden |
|---|---|---|
| `visited_urls` set'i | `threading.Lock` | İki thread aynı URL'yi aynı anda eklemesin |
| `[letter].data` dosyaları | `threading.Lock` | İki thread aynı dosyaya aynı anda yazmasın (veri bozulması) |
| `jobs/{id}.data` log dosyası | `threading.Lock` | Log yazımları üst üste binmesin |
| BFS kuyruğu | `queue.Queue` (dahili güvenli) | Kuyruğun kendisi zaten thread-safe |

**Lock nasıl çalışıyor:**
```python
lock = threading.Lock()

# Thread A                     # Thread B
with lock:                     #   (bekliyor...)
    dosyaya_yaz()              #   (bekliyor...)
# lock serbest                 with lock:
#                                  dosyaya_yaz()
```
Bir thread `with lock:` bloğuna girdiğinde, diğer thread'ler o blok bitene kadar **bekler**. Bu sayede aynı dosyaya aynı anda iki thread yazmaz.

---

## Dosya Sistemi Yapısı

Crawler çalıştıktan sonra `data/` klasörü şu hale gelir:

```
data/
├── visited_urls.data           ← Ziyaret edilen tüm URL'ler (satır satır)
├── jobs/
│   └── 1774120068_14062...data ← Job durumu + loglar (JSON)
└── storage/
    ├── a.data                  ← "a" ile başlayan kelimelerin indexi
    ├── e.data                  ← "e" ile başlayan kelimeler
    ├── h.data                  ← "h" ile başlayan kelimeler
    └── ...                     ← Her harf için bir dosya
```

**Job dosyası örneği (`data/jobs/123_456.data`):**
```json
{
  "crawler_id": "123_456",
  "status": "completed",
  "max_depth": 2,
  "processed": 5,
  "errors": 0,
  "queue_size": 0,
  "logs": [
    {"type": "fetch", "url": "https://example.com", "depth": 0, "timestamp": 1774120068.5},
    {"type": "fetched", "url": "https://example.com", "depth": 0, "status": 200, "size": 1256},
    {"type": "indexed", "url": "https://example.com", "depth": 0, "words": 42, "links_found": 3},
    {"type": "enqueued", "depth": 1, "new_links": 3, "queue_size": 3},
    {"type": "status", "message": "Crawl completed", "processed": 5, "errors": 0}
  ]
}
```

---

## Docker Yapısı

Projede Python kurulu olmasına gerek yok — her şey Docker container'ında çalışıyor:

| Dosya | Ne Yapıyor |
|---|---|
| `Dockerfile` | `python:3.11-alpine` base image, non-root user, sadece `src/` ve `tests/` kopyalar |
| `docker-compose.yml` | Servisi tanımlar, port 8080 açar, `./data` klasörünü volume olarak bağlar |
| `.dockerignore` | `.git`, `__pycache__`, `data/` gibi gereksiz dosyaları container'a sokmaz |
| `Makefile` | `make build`, `make up`, `make test` gibi kısa komutlar |

**Volume mount (`./data:/app/data`):** Container silinse bile `data/` klasöründeki crawl verileri host makinede kalır.

---

## Searcher (Arama Motoru)

Checkpoint 1'in parçası olmasa da, crawler'ın ürettiği veriyi arayabilmek için arama modülü de yazıldı:

- `src/searcher/index_reader.py` → `[letter].data` dosyalarını `threading.RLock` ile thread-safe okur
- `src/searcher/search.py` → Sorguyu kelimelere ayırır, ilgili dosyaları okur, frekansa göre sıralar

```python
search("python", page=1, size=10)
# → {"results": [{"url": "...", "origin_url": "...", "depth": 1, "frequency": 5}], "total": 1, "page": 1}
```

---

## Checkpoint 1 Durumu

| Gereksinim | Durum |
|---|---|
| Proje klasör yapısı | ✅ |
| `visited_store.py` — thread-safe visited URL seti | ✅ |
| `fetcher.py` — urllib.request ile HTTP fetch | ✅ |
| `parser.py` — HTMLParser ile link + kelime çıkarma | ✅ |
| `file_store.py` — JSON satırı olarak kelime indexi yazma | ✅ |
| `queue_manager.py` — Back pressure ile BFS kuyruğu | ✅ |
| `worker.py` — BFS worker, derinlik kontrolü | ✅ |
| `crawler.py` — Thread'de job başlatma, crawler ID üretimi | ✅ |
| Aynı URL iki kez ziyaret edilmiyor | ✅ |
| Back pressure devreye giriyor | ✅ |
| Thread safety — eş zamanlı yazma güvenli | ✅ |
| 60/60 test geçiyor | ✅ |
