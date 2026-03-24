# CHECK_3 — Checkpoint 3 Raporu: Real-Time Dashboard UI + Tam Entegrasyon

> **Proje:** Google in One Day — Python Edition  
> **Checkpoint:** 3 — Real-Time Dashboard UI + Tam Entegrasyon  
> **Tarih:** 21 Mart 2026

---

## Ne Yaptık?

Checkpoint 1'de crawler motoru, Checkpoint 2'de API katmanı inşa etmiştik. Bu son checkpoint'te **kullanıcıya dönük tarayıcı arayüzünü** oluşturduk. Artık kullanıcı tarayıcıdan `http://localhost:8080` adresine gidip crawler başlatabiliyor, logları canlı izleyebiliyor ve sonuçları arayabiliyor — tek bir komutla (`python src/api/server.py` veya `docker-compose up`). Proje teslime hazır hale getirildi: PRD, recommendation, .gitignore, requirements.txt dosyaları oluşturuldu.

---

## Bu Checkpoint'te Eklenen / Değişen Dosyalar

| Dosya | Tür | Ne Yapıyor |
|---|---|---|
| `src/ui/static/index.html` | Yeni | Crawler Dashboard — form + job listesi |
| `src/ui/static/status.html` | Yeni | Canlı log akışı + metrikler (long polling) |
| `src/ui/static/search.html` | Yeni | Arama kutusu + paginated sonuçlar |
| `product_prd.md` | Yeni | Formal Ürün Gereksinimleri Dokümanı |
| `recommendation.md` | Yeni | 2 paragraflık production roadmap |
| `.gitignore` | Yeni | data/, __pycache__, IDE dosyaları |
| `requirements.txt` | Yeni | Boş (sadece stdlib kullanılıyor) |

---

## Dosya Dosya Ne Yapıyor

### 1. `src/ui/static/index.html` — Crawler Dashboard

**Tek iş:** Kullanıcının yeni crawl job'ı başlatması ve mevcut job'ları görmesi.

**Sayfa yapısı:**
```
┌─────────────────────────────────────────────┐
│ 🕷️ Crawler    [Dashboard]    [Search]       │  ← Navbar
├─────────────────────────────────────────────┤
│ New Crawl Job                               │
│ ┌─────────────────────────────────────────┐ │
│ │ Seed URL: [https://example.com  ]       │ │
│ │ Depth:    [2]                           │ │
│ │ [🚀 Start Crawl]                        │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ Job History                                 │
│ ┌────────┬──────────┬─────┬────┬─────┬────┐ │
│ │ ID     │ Status   │ Proc│ Err│Depth│ Act│ │
│ │ 177... │ running  │  3  │  0 │  2  │View│ │
│ │ 177... │completed │  12 │  1 │  3  │View│ │
│ └────────┴──────────┴─────┴────┴─────┴────┘ │
└─────────────────────────────────────────────┘
```

**Nasıl çalışıyor:**

1. **Form submit:** Kullanıcı URL ve depth girip "Start Crawl" butonuna tıklıyor
2. JavaScript `fetch('/crawl', {method: 'POST', body: JSON.stringify({url, depth})})` yapıyor
3. API `201 Created` dönünce yeşil başarı mesajı gösteriliyor
4. Hata dönerse (400, 500) kırmızı hata mesajı gösteriliyor

5. **Job listesi:** `setInterval(loadJobs, 3000)` → her 3 saniyede `GET /crawl/list` çağrılıyor
6. Gelen JSON'daki her job bir tablo satırı olarak render ediliyor
7. Status badge'leri renkli:
   - 🟢 `running` → yeşil arka plan
   - 🔵 `completed` → mavi arka plan
   - 🔴 `error` → kırmızı arka plan
8. "View Logs" linki → `/status?id={crawler_id}` sayfasına yönlendiriyor

**Neden 3 saniye aralık:**
- Çok sık olursa sunucuya gereksiz yük biner
- Çok seyrek olursa kullanıcı güncel durumu göremez
- 3 saniye iyi bir denge — job listesi zaten hafif bir endpoint

---

### 2. `src/ui/static/status.html` — Canlı Log Akışı + Metrikler

**Tek iş:** Belirli bir crawler job'ının loglarını gerçek zamanlı göstermek ve metriklerini takip etmek.

**Sayfa yapısı:**
```
┌─────────────────────────────────────────────┐
│ Job Status  [running]                       │
│ 1774120068_140626653346616                  │  ← Crawler ID
├─────────────────────────────────────────────┤
│ ┌─────────┐ ┌─────────┐ ┌─────────┐        │
│ │    3    │ │    7    │ │   OFF   │        │
│ │URLs Proc│ │Queue Sz │ │Back Pres│        │  ← Metrik kartları
│ ├─────────┤ ├─────────┤ ├─────────┤        │
│ │    0    │ │    2    │                    │
│ │ Errors  │ │Max Depth│                    │
│ └─────────┘ └─────────┘                    │
├─────────────────────────────────────────────┤
│ Live Logs                                   │
│ ┌─────────────────────────────────────────┐ │
│ │ 14:32:01 [fetch]   Fetching example.com │ │
│ │ 14:32:02 [fetched] OK example.com 1.2KB │ │
│ │ 14:32:02 [indexed] 42 words, 3 links    │ │
│ │ 14:32:03 [enqueued] +3 links, queue=3   │ │
│ │ 14:32:04 [back_pressure] ⚠ Queue full   │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ← Back to Dashboard                        │
└─────────────────────────────────────────────┘
```

**Nasıl çalışıyor:**

1. **Job ID:** URL'deki `?id=...` parametresinden alınıyor (`new URLSearchParams(window.location.search)`)
2. **Long polling:** `setInterval(poll, 2000)` → her 2 saniyede `GET /crawl/{id}?since={offset}` çağrılıyor
3. **`since` parametresi:** İlk çağrıda `since=0` gönderiliyor, API tüm logları döndürüyor. Sonraki çağrılarda `since=N` (N = şu ana kadar alınan log sayısı) gönderiliyor → sadece yeni loglar geliyor
4. **Neden long polling:** WebSocket stdlib'de yok. Alternatif olarak kısa aralıklı HTTP polling yapıyoruz. `since` parametresi sayesinde her seferinde tüm logları çekmiyoruz — sadece yeni olanları.

**Metrik kartları:**
| Metrik | Veri Kaynağı | Açıklama |
|---|---|---|
| URLs Processed | `data.processed` | İşlenmiş toplam URL sayısı |
| Queue Size | `data.queue_size` | Kuyrukta bekleyen URL sayısı |
| Back Pressure | Log'larda `back_pressure` tipi var mı | Kuyruk dolunca ACTIVE, yoksa OFF |
| Errors | `data.errors` | Toplam hata sayısı |
| Max Depth | `data.max_depth` | Tarama derinlik limiti |

**Log renklendirmesi:**
| Log Tipi | Renk | Anlamı |
|---|---|---|
| `fetch` | 🔵 Mavi | URL indiriliyor |
| `fetched` | 🟢 Yeşil | Başarıyla indirildi |
| `indexed` | 🟣 Mor | Kelimeler indekslendi |
| `enqueued` | 🟡 Sarı | Yeni linkler kuyruğa eklendi |
| `back_pressure` | 🟠 Turuncu | Kuyruk dolu — bekle |
| `error` / `fetch_error` | 🔴 Kırmızı | Hata oluştu |
| `status` | 🔵 Mavi (kalın) | Durum değişikliği (completed vb.) |

**Tamamlanma algılama:**
- `data.status === 'completed'` veya `'error'` geldiğinde `clearInterval(pollInterval)` çağrılıyor
- Polling duruyor, sayfa donuklaşmıyor
- Badge son durumu gösteriyor (completed/error)

---

### 3. `src/ui/static/search.html` — Arama Sayfası

**Tek iş:** Kullanıcının arama yapması ve sonuçları sayfalanmış tabloda görmesi.

**Sayfa yapısı:**
```
┌─────────────────────────────────────────────┐
│ 🔍 Search Index                             │
│ ┌─────────────────────────────┬──────────┐  │
│ │ python crawler              │ [Search] │  │
│ └─────────────────────────────┴──────────┘  │
│                                             │
│ 12 results for "python crawler" — Page 1/2  │
│ ┌───────────┬───────────┬─────┬──────────┐  │
│ │ URL       │ Origin    │Depth│ Frequency│  │
│ │ a.com/py  │ root.com  │  1  │ ████ 8   │  │
│ │ b.com/doc │ a.com/py  │  2  │ ███  5   │  │
│ │ c.com/api │ root.com  │  1  │ ██   3   │  │
│ └───────────┴───────────┴─────┴──────────┘  │
│                                             │
│         [← Prev]  Page 1/2  [Next →]       │
└─────────────────────────────────────────────┘
```

**Nasıl çalışıyor:**

1. **Form submit:** Kullanıcı arama kutusuna kelime(ler) yazıp Enter veya "Search" butonuna basar
2. JavaScript `fetch(/search?q=${query}&page=${page}&size=10)` çağrısı yapar
3. Gelen JSON'daki `results` dizisi tablo satırlarına çevrilir

**Frekans çubuğu (frequency bar):**
```javascript
maxFreq = Math.max(...data.results.map(r => r.frequency || 1));
barW = Math.max(4, Math.round((r.frequency / maxFreq) * 80));
```
- En yüksek frekanslı sonucun çubuğu 80px genişliğinde
- Diğerleri oransal olarak daha kısa
- Minimum genişlik 4px (sıfır sonuç olmaması için)
- Bu görsel gösterim, kullanıcının hangi sonucun daha alakalı olduğunu hızlıca görmesini sağlar

**Pagination:**
- `currentPage` state'i JavaScript'te tutuluyor
- "Prev" ve "Next" butonları `doSearch(currentPage ± 1)` çağırıyor
- İlk sayfadayken "Prev" disabled, son sayfadayken "Next" disabled
- Toplam sayfa sayısı: `Math.ceil(total / pageSize)`

**Boş durum yönetimi:**
- Sayfa yüklendiğinde: "Enter a search query to find indexed pages."
- Arama yapılıp sonuç yoksa: "No results found."
- Hata olursa: console.error ile loglanıyor

---

## Static Dosya Sunumu — Server Entegrasyonu

**server.py'deki static handler'lar:**

```python
# Route tanımları
router.get('/', handle_index)          # → index.html
router.get('/status', handle_status_page)   # → status.html
router.get('/search-ui', handle_search_ui)  # → search.html
```

**`_serve_static()` fonksiyonu:**
1. Dosya yolunu oluştur: `src/ui/static/{filename}`
2. Dosya var mı kontrol et (`os.path.isfile`)
3. Yoksa → `404 Not Found`
4. Uzantıya göre MIME type belirle (`.html` → `text/html`)
5. Dosyayı oku ve yanıt olarak gönder

**Neden ayrı route'lar (tek bir wildcard değil):**
- Güvenlik: sadece bilinen dosyalar servis ediliyor, path traversal riski yok
- Açıklık: her route'un ne döndürdüğü server.py'de açıkça görülüyor
- API route'ları ile çakışma riski yok

---

## End-to-End Akış — Tüm Sistem

```
Kullanıcı (Tarayıcı)
    │
    ├──[1] GET / ──────────────────────────→ index.html yüklendi
    │
    ├──[2] POST /crawl {url, depth} ───────→ start_crawl() → Thread başlatıldı
    │                                         ↓
    │                                   ┌─────────────────┐
    │                                   │ BFS Worker       │
    │                                   │ fetch → parse    │
    │                                   │ → index → enqueue│
    │                                   │ → job dosyasına  │
    │                                   │   log yaz        │
    │                                   └─────────────────┘
    │
    ├──[3] GET /crawl/list ────────────────→ Job listesi (her 3s)
    │       ↓
    │   Tabloda job'lar görünüyor
    │   "View Logs" tıkla
    │       ↓
    ├──[4] GET /status?id=123_456 ─────────→ status.html yüklendi
    │
    ├──[5] GET /crawl/123_456?since=0 ─────→ Tüm loglar (ilk çağrı)
    ├──[6] GET /crawl/123_456?since=5 ─────→ Sadece yeni loglar (her 2s)
    ├──[7] GET /crawl/123_456?since=12 ────→ Sadece yeni loglar
    │       ↓
    │   Metrikler güncelleniyor
    │   Loglar aşağı akıyor
    │   "completed" → polling durdu
    │
    ├──[8] GET /search-ui ─────────────────→ search.html yüklendi
    │
    ├──[9] GET /search?q=python&page=1 ────→ Sonuçlar geldi
    │       ↓
    │   Tablo + frekans çubukları
    │   Pagination: [← Prev] Page 1/3 [Next →]
    │
    └──[10] GET /search?q=python&page=2 ───→ 2. sayfa sonuçları
```

---

## Dashboard Metrikleri — Nereden Geliyor

UI'daki her metrik, API yanıtındaki bir alandan besleniyor:

```
GET /crawl/{id}?since=0
→ {
    "crawler_id": "1774120068_14062...",
    "status": "running",           ← Badge rengi
    "processed": 3,                ← "URLs Processed" kartı
    "errors": 0,                   ← "Errors" kartı
    "max_depth": 2,                ← "Max Depth" kartı
    "queue_size": 7,               ← "Queue Size" kartı
    "logs": [
      {"type": "back_pressure"},   ← "Back Pressure" kartı = ACTIVE
      ...
    ]
  }
```

**Back Pressure algılama mantığı:**
```javascript
const hasBP = logs.some(l => l.type === 'back_pressure');
```
Gelen log'lardan herhangi birinde `type === 'back_pressure'` varsa kart "ACTIVE" ve sarı gösteriliyor. Crawler tamamlanınca "OFF" ve mavi'ye dönüyor.

---

## UI Tasarım Kararları

| Karar | Neden |
|---|---|
| Dark theme | Terminal/geliştirici aracı hissi; crawler izleme sayfasına uygun |
| Navbar ile 3 sayfa | Tek sayfa yerine ayrı sayfalar — her birinin tek sorumluluğu var |
| CSS-in-HTML (inline style bloğu) | Harici CSS dosyası yok — tek HTML dosyası yeterli, ekstra route gerekmez |
| JavaScript-in-HTML (inline script) | Harici JS dosyası yok — aynı sebep |
| `fetch()` API | XMLHttpRequest yerine modern, Promise tabanlı, daha okunabilir |
| `setInterval` polling | WebSocket stdlib'de yok; timer + `?since=N` ile verimli polling |
| Frekans çubuğu (bar) | Sayısal değer tek başına yeterli değil — görsel karşılaştırma çok daha hızlı |
| Badge renkleri (yeşil/mavi/kırmızı) | Durum bilgisi metinden önce renk ile algılanıyor |

---

## Teslim Dosyaları

### `product_prd.md` — Ürün Gereksinimleri Dokümanı

Formal PRD dokümanı. İçindekiler:
- Ürün tanımı ve hedef
- İşlevsel gereksinimler (Crawler, Search, API, UI)
- İşlevsel olmayan gereksinimler (thread safety, back pressure, persistence)
- Teknik kısıtlamalar (stdlib only, no 3rd party)
- Başarı kriterleri

### `recommendation.md` — Production Roadmap

2 paragraflık özet:
1. **Altyapı:** Filesystem → NoSQL + Trie; horizontal scaling; region-isolate crawler node'ları
2. **Arama + Gözlemlenebilirlik:** PageRank, fuzzy search; Prometheus + Grafana; rate limiting, DDoS koruması

### `.gitignore`

```
data/
__pycache__/
*.pyc
.env
*.egg-info/
dist/
build/
.idea/
.vscode/
```
`data/` klasörü git'e dahil edilmiyor — crawl verileri kullanıcının kendi ortamında üretiliyor.

### `requirements.txt`

**Boş dosya.** Proje sadece Python standart kütüphanesini kullanıyor. `pip install -r requirements.txt` herhangi bir 3rd party paket yüklemeyecek. Bu bilinçli bir tasarım kararı.

---

## Neden Flask/React Kullanmadık?

| Alternatif | Kullanmadık Çünkü |
|---|---|
| Flask / FastAPI | README açıkça 3rd party framework yasağı koyuyor |
| React / Vue | JavaScript framework'leri yasak; inline JS yeterli |
| Jinja2 templates | 3rd party; düz HTML + JS aynı işi yapıyor |
| WebSocket | `websockets` kütüphanesi 3rd party; stdlib'de WS yok |
| Bootstrap CSS | CDN bağımlılığı; inline CSS çalışma ortamı bağımsız |

**Sonuç:** Tüm UI 3 HTML dosyası, toplam ~600 satır. Hiçbir dış bağımlılık yok. Tarayıcı açınca hemen çalışıyor.

---

## Docker ile Tam Çalıştırma

```bash
# Tek komutla başlat
docker-compose up -d

# Tarayıcıda aç
http://localhost:8080          → Crawler Dashboard
http://localhost:8080/status   → Job Status (id gerekli)
http://localhost:8080/search-ui → Search Page

# Testleri çalıştır
docker-compose run --rm crawler-app python -m unittest discover -s tests -v

# Durdur
docker-compose down
```

**Fresh clone testi:**
```bash
git clone [repo-url] fresh-test
cd fresh-test
docker-compose up -d
# http://localhost:8080 açılır, crawl başlatılabilir, arama yapılabilir
```

`data/` klasörü `.gitignore`'da olduğu için repo'da yok. İlk `docker-compose up` çalıştığında Dockerfile içindeki `RUN mkdir -p data/jobs data/storage` komutu klasörleri oluşturuyor. Volume mount (`./data:/app/data`) sayesinde veriler host'ta da kalıyor.

---

## Test Durumu

```
Ran 79 tests in 23.595s
OK
```

Tüm 79 test geçiyor:

| Test Dosyası | Test Sayısı | Kapsam |
|---|---|---|
| `test_fetcher.py` | 6 | HTTP fetch, timeout, content-type filtresi |
| `test_parser.py` | 12 | Link/kelime çıkarma, filtreleme, fragment temizleme |
| `test_visited_store.py` | 7 | Thread safety, persistence, duplicate kontrolü |
| `test_file_store.py` | 9 | JSON Lines yazım, batch yazım, concurrent writes |
| `test_queue_manager.py` | 11 | FIFO, back pressure, maxsize, timeout |
| `test_crawler.py` | 6 | End-to-end crawler, job dosyası, derinlik limiti |
| `test_search.py` | 11 | Arama, sıralama, pagination, aggregation |
| `test_api.py` | 19 | REST API endpoint'leri, router, CORS, hata kodları |
| **Toplam** | **79** | |

---

## Checkpoint 3 Durumu

| Gereksinim | Durum |
|---|---|
| `index.html` — Crawler Dashboard, form + job listesi | ✅ |
| `status.html` — Canlı log akışı (long polling), metrikler | ✅ |
| `search.html` — Arama kutusu, paginated sonuçlar | ✅ |
| Static dosya sunumu server'a entegre | ✅ |
| İşlenen URL sayısı / kuyruk derinliği metrikleri | ✅ |
| Back pressure göstergesi (aktif/pasif) | ✅ |
| Job durumu badge'leri (running/completed/error) | ✅ |
| `product_prd.md` tamamlandı | ✅ |
| `recommendation.md` tamamlandı (2 paragraf) | ✅ |
| `.gitignore` oluşturuldu (data/ dahil) | ✅ |
| `requirements.txt` oluşturuldu (boş — stdlib only) | ✅ |
| End-to-end akış: crawl → status → search çalışıyor | ✅ |
| 79/79 test geçiyor | ✅ |
| **🎉 Proje tamamlandı!** | ✅ |
