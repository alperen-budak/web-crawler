# CHECK_2 — Checkpoint 2 Raporu: Search Engine + HTTP API

> **Proje:** Google in One Day — Python Edition  
> **Checkpoint:** 2 — Search Engine + HTTP API  
> **Tarih:** 21 Mart 2026

---

## Ne Yaptık?

Checkpoint 1'de inşa ettiğimiz crawler motorunun üzerine iki büyük katman ekledik:

1. **Arama Motoru (Searcher):** Crawler'ın diske yazdığı kelime index'ini okuyan, frekansa göre sıralayan, pagination destekli bir query engine.
2. **HTTP API Sunucusu:** Tüm sistemi dışarıya açan REST API — crawler başlatma, job durumu sorgulama ve arama yapma. Saf `http.server` modülü ile, Flask/FastAPI olmadan.

Artık sistem bir terminal komutu değil; `http://localhost:8080` üzerinden çalışan bir web servisi.

---

## Bu Checkpoint'te Eklenen Teknolojiler

| Teknoloji | Nereden Geliyor | Ne İşe Yarıyor |
|---|---|---|
| `http.server.HTTPServer` | Python stdlib | TCP soket dinleyen HTTP sunucu |
| `http.server.BaseHTTPRequestHandler` | Python stdlib | Gelen HTTP isteklerini işleyen handler sınıfı |
| `urllib.parse.urlparse` / `parse_qs` | Python stdlib | URL path ve query string ayrıştırma |
| `threading.RLock` | Python stdlib | Arama motoru okurken crawler yazabilsin (re-entrant lock) |
| `re` (regex) | Python stdlib | URL routing — path parametrelerini çıkarmak için |
| `json` | Python stdlib | Request/response body'lerini parse etmek ve oluşturmak |

---

## Dosya Dosya Ne Yapıyor

### 1. `src/api/router.py` — URL Yönlendirici

**Tek iş:** Gelen HTTP isteğinin method + path'ine bakıp doğru handler fonksiyonuna yönlendirmek.

```python
router = Router()
router.post('/crawl', handle_crawl_start)
router.get('/crawl/list', handle_crawl_list)
router.get('/crawl/{id}', handle_crawl_status)   # {id} = path parametresi
router.get('/search', handle_search)
```

**Nasıl çalışıyor:**
- Her route kaydedilirken pattern'deki `{param}` ifadeleri regex'e çevriliyor:
  - `/crawl/{id}` → `/crawl/(?P<id>[^/]+)`
- İstek geldiğinde tüm route'lar sırayla deneniyor
- İlk eşleşen route'un handler'ı çağrılıyor, path parametreleri `**kwargs` ile aktarılıyor
- **Sıralama önemli:** `/crawl/list` route'u `/crawl/{id}` route'undan **önce** tanımlanmış — yoksa "list" kelimesi bir ID olarak algılanır

**Neden bu tasarım:**
Flask/FastAPI kullanamıyoruz. Ama yine de temiz bir route yapısı istiyoruz. Bu router, decorator tabanlı framework'lerin yaptığı işi 75 satırda yapıyor.

---

### 2. `src/api/handlers.py` — İstek İşleyicileri

**Tek iş:** Her endpoint için iş mantığını çalıştırıp JSON yanıt döndürmek.

Her handler'ın yapısı aynı:
```
1. İstek parametrelerini oku (body veya query string)
2. Parametreleri doğrula (eksik/geçersiz → 400 hatası)
3. İş mantığını çalıştır (crawl başlat, arama yap, dosya oku)
4. JSON yanıtı gönder
```

**Yardımcı fonksiyonlar:**

| Fonksiyon | Ne Yapıyor |
|---|---|
| `_send_json(handler, data, status)` | JSON yanıtı HTTP response olarak yazar |
| `_send_error(handler, message, status)` | `{"error": "..."}` formatında hata yanıtı |
| `_parse_query(handler)` | URL'deki `?q=test&page=1` gibi query parametrelerini dict olarak döndürür |
| `_read_body(handler)` | POST request body'sini okur |

**Her endpoint ne yapıyor:**

#### `POST /crawl` — Crawler Job Başlatma

```
İstek:  {"url": "https://example.com", "depth": 2, "max_queue": 100, "rate": 1.0}
Yanıt:  {"crawler_id": "1774120068_14062...", "status": "running"}  (201 Created)
```

Akış:
1. Body'den JSON oku
2. `url` alanını kontrol et — boş mu? `http://` ile mi başlıyor?
3. `depth`, `max_queue`, `rate` parametrelerini doğrula
4. `start_crawl()` fonksiyonunu çağır → arka plan thread'i başlatılır
5. Dönen `crawler_id`'yi JSON olarak yanıtla

**Hata durumları:**
- Body boş → `400 Request body is required`
- URL eksik → `400 Missing required field: url`
- URL geçersiz → `400 Invalid URL: must start with http:// or https://`
- depth aralık dışı → `400 depth must be between 0 and 10`

#### `GET /crawl/list` — Job Listesi

```
Yanıt:  {"jobs": [{"crawler_id": "...", "status": "completed", "processed": 5}, ...]}
```

Akış:
1. Bellekteki aktif job'ları al (`list_jobs()`)
2. `data/jobs/` dizinindeki dosyaları tara (sunucu restart'ından sağ kalması için)
3. Her job dosyasını oku, özet bilgilerini çıkar
4. Epoch'a göre sırala (en yeni en üstte)

#### `GET /crawl/{id}` — Job Durumu + Loglar

```
Yanıt:  {"crawler_id": "...", "status": "running", "processed": 3, "logs": [...]}
```

**Long polling desteği:**
```
GET /crawl/12345_678?since=5
→ Sadece 5. index'ten sonraki logları döndürür
```

Bu, UI'ın canlı log akışı yapmasını sağlar: her 2 saniyede `?since=N` ile sadece yeni logları çeker, tüm listeyi değil.

#### `GET /search?q=...&page=1&size=10` — Arama

```
Yanıt:  {"results": [{"url": "...", "origin_url": "...", "depth": 1, "frequency": 5}], "total": 12, "page": 1}
```

Akış:
1. `q` parametresini oku — boşsa `400` hata
2. `page` ve `size` parametrelerini integer'a çevir
3. `search()` fonksiyonunu çağır
4. Sonuçları JSON olarak döndür

---

### 3. `src/api/server.py` — HTTP Sunucu

**Tek iş:** Port 8080'de dinle, gelen istekleri Router'a yönlendir, static dosyaları servis et.

```python
class APIRequestHandler(BaseHTTPRequestHandler):
    def do_GET(self):     # GET istekleri
        self._dispatch('GET')
    
    def do_POST(self):    # POST istekleri
        self._dispatch('POST')
    
    def do_OPTIONS(self):  # CORS preflight
        # 204 + CORS header'ları
    
    def _dispatch(self, method):
        handler_func, params = router.resolve(method, self.path)
        if handler_func:
            handler_func(self, **params)
        else:
            # 404 Not Found
```

**Nasıl çalışıyor:**
- `HTTPServer(('0.0.0.0', 8080), APIRequestHandler)` → TCP soket açıp dinliyor
- Her istek geldiğinde Python otomatik olarak yeni bir `APIRequestHandler` instance'ı oluşturuyor
- `do_GET` veya `do_POST` çağrılıyor → `_dispatch` → Router → Handler
- **CORS:** Tarayıcıdan JavaScript `fetch()` çağrıları için `Access-Control-Allow-Origin: *` header'ı ekleniyor
- **Exception handling:** Handler'da hata olursa → `500 Internal Server Error` JSON yanıtı (sunucu çökmez)

**Static dosya sunumu:**
```
GET /          → src/ui/static/index.html
GET /status    → src/ui/static/status.html
GET /search-ui → src/ui/static/search.html
```

MIME type'lar dosya uzantısına göre otomatik ayarlanıyor (`.html` → `text/html`, `.js` → `application/javascript`).

---

### 4. `src/searcher/index_reader.py` — Index Okuyucu

**Tek iş:** `data/storage/[letter].data` dosyalarını thread-safe olarak okumak.

```python
reader = IndexReader()
entries = reader.read('p')           # p.data'daki tüm kayıtlar
entries = reader.read_word('python') # sadece "python" kelimesinin kayıtları
```

**Neden `threading.RLock` kullanıyoruz (Lock değil):**
- `Lock`: Bir thread kilidi alınca, **aynı thread bile** tekrar alamaz → deadlock riski
- `RLock` (Re-entrant Lock): Aynı thread kilidi birden fazla kez alabilir
- Arama motoru iç içe okuma yapabilir (read → read_word → read) — RLock bunu güvenli kılıyor
- Crawler yazarken search okuyabiliyor — her ikisi farklı thread'lerde, RLock sırayla erişim sağlıyor

---

### 5. `src/searcher/search.py` — Arama Motoru

**Tek iş:** Sorguyu kelimelere ayır, her kelime için index'i oku, frekansa göre sırala, sayfalanmış sonuç döndür.

```python
search("python crawler", page=1, size=10)
```

**Akış adım adım:**

```
1. Sorgu: "python crawler"
2. Tokenize: ["python", "crawler"]
3. Her kelime için:
   - "python" → p.data dosyasını oku → "python" ile eşleşenleri filtrele
   - "crawler" → c.data dosyasını oku → "crawler" ile eşleşenleri filtrele
4. Tüm sonuçları birleştir
5. Aynı URL'ye ait kayıtların frekanslarını topla
6. Frekansa göre azalan sırala (en alakalı en üstte)
7. Sayfalama: results[(page-1)*size : page*size]
8. Döndür: {"results": [...], "total": 12, "page": 1}
```

**Frekans birleştirme örneği:**
```
p.data: {"word": "python", "url": "https://a.com", "freq": 5}
p.data: {"word": "python", "url": "https://a.com", "freq": 3}
→ Birleşik: {"url": "https://a.com", "frequency": 8}
```

Aynı URL'de aynı kelime birden fazla kez indexlenmişse (farklı crawl derinliklerinden), frekanslar toplanıyor.

---

## İstek-Yanıt Akışı — Büyük Resim

```
Tarayıcı / curl / fetch()
    │
    │  HTTP Request
    ▼
┌──────────────────────────────────────────────┐
│  HTTPServer (:8080)                          │
│  BaseHTTPRequestHandler                      │
│                                              │
│  do_GET() / do_POST()                        │
│       │                                      │
│       ▼                                      │
│  ┌─────────────┐                             │
│  │   Router     │  resolve(method, path)     │
│  │ /crawl      →│→ handle_crawl_start        │
│  │ /crawl/list →│→ handle_crawl_list         │
│  │ /crawl/{id} →│→ handle_crawl_status       │
│  │ /search     →│→ handle_search             │
│  │ /           →│→ index.html                │
│  └──────┬──────┘                             │
│         │                                    │
│         ▼                                    │
│  ┌──────────────┐    ┌────────────────┐      │
│  │  handlers.py  │    │  search.py     │      │
│  │               │    │                │      │
│  │ crawl_start   │    │ tokenize →     │      │
│  │ → start_crawl │    │ read index →   │      │
│  │ → thread başla│    │ sort by freq → │      │
│  │               │    │ paginate →     │      │
│  │ crawl_status  │    │ return results │      │
│  │ → job dosyası │    │                │      │
│  │   oku         │    └────────────────┘      │
│  └──────────────┘                             │
│         │                                     │
│         ▼                                     │
│  _send_json(data, status_code)                │
│  → Content-Type: application/json             │
│  → CORS headers                               │
│  → HTTP yanıt                                 │
└──────────────────────────────────────────────┘
```

---

## API Endpoint Tablosu

| Method | Endpoint | İstek | Yanıt | Hata |
|---|---|---|---|---|
| `POST` | `/crawl` | `{"url": "...", "depth": 2}` | `201 {"crawler_id": "...", "status": "running"}` | `400 {"error": "..."}` |
| `GET` | `/crawl/list` | — | `200 {"jobs": [...]}` | — |
| `GET` | `/crawl/{id}` | `?since=N` (opsiyonel) | `200 {status, logs, processed, ...}` | `404 {"error": "Job not found"}` |
| `GET` | `/search` | `?q=python&page=1&size=10` | `200 {"results": [...], "total": N, "page": N}` | `400 {"error": "Missing q"}` |
| `GET` | `/` | — | `200 index.html` | `404` (dosya yoksa) |
| `GET` | `/status` | — | `200 status.html` | `404` |
| `GET` | `/search-ui` | — | `200 search.html` | `404` |
| `OPTIONS` | herhangi | — | `204` + CORS headers | — |

---

## Live Indexing — Crawler Yazarken Arama Nasıl Çalışıyor

```
Thread A (Crawler)                Thread B (Search API)
─────────────────                ─────────────────────
file_store.write_word()          index_reader.read_word()
  │                                │
  ▼                                ▼
  Lock.acquire()                   RLock.acquire()
  dosyaya yaz ──┐                  ── bekle...
  Lock.release() │                 RLock.acquire() ← artık okuyabilir
                 │                 dosyadan oku
                 │                 RLock.release()
                 ▼
  Yeni veri diske yazıldı         Yeni veri okundu
```

FileStore yazma için `threading.Lock`, IndexReader okuma için `threading.RLock` kullanıyor. Yazma bittiği anda okuma yeni veriyi görüyor. Crawler aktifken arama yapılabiliyor — sistem çökmüyor.

---

## Hata Yönetimi

| Senaryo | Ne Oluyor | HTTP Kodu |
|---|---|---|
| Body boş | `{"error": "Request body is required"}` | 400 |
| URL eksik | `{"error": "Missing required field: url"}` | 400 |
| URL geçersiz (http:// yok) | `{"error": "Invalid URL: ..."}` | 400 |
| Bilinmeyen job ID | `{"error": "Job not found: ..."}` | 404 |
| Bilinmeyen path | `{"error": "Not found: GET /xyz"}` | 404 |
| Handler'da exception | `{"error": "Internal server error: ..."}` | 500 |
| Arama parametresi eksik | `{"error": "Missing required query parameter: q"}` | 400 |

Hiçbir hata durumunda sunucu çökmüyor — tüm hatalar yakalanıp JSON olarak döndürülüyor.

---

## CORS (Cross-Origin Resource Sharing)

Tarayıcıdan JavaScript ile API'ye istek yapabilmek için her yanıta eklenen header:

```
Access-Control-Allow-Origin: *
```

`OPTIONS` preflight isteklerine `204 No Content` ile yanıt veriliyor + ek CORS header'ları:
```
Access-Control-Allow-Methods: GET, POST, OPTIONS
Access-Control-Allow-Headers: Content-Type
```

Bu sayede `index.html` sayfasından `fetch('/crawl', {method: 'POST', ...})` çağrısı başarılı oluyor.

---

## Checkpoint 2 Durumu

| Gereksinim | Durum |
|---|---|
| `index_reader.py` — RLock ile thread-safe okuma | ✅ |
| `search.py` — tokenize → oku → sırala → paginate | ✅ |
| Live indexing: crawler yazarken search okuyabiliyor | ✅ |
| Pagination: `page` ve `size` parametreleri | ✅ |
| `server.py` — `BaseHTTPRequestHandler` tabanlı sunucu | ✅ |
| `handlers.py` — tüm endpoint handler'ları | ✅ |
| `router.py` — regex tabanlı URL routing | ✅ |
| `POST /crawl` — job başlatma | ✅ |
| `GET /crawl/list` — job listesi | ✅ |
| `GET /crawl/{id}` — job durumu + long polling | ✅ |
| `GET /search` — arama sonuçları | ✅ |
| Hata yönetimi — uygun HTTP kodları | ✅ |
| Eş zamanlı crawler + search çökmüyor | ✅ |
| 79/79 test geçiyor | ✅ |
