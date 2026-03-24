# 🕷️ Project 1: Google in One Day — Python Edition

> **Istanbul Technical University — AI Aided Computer Engineering Course**
> Instructor: David Doğukan Erenel | March 2026
> AI Tool: GitHub Copilot
> Language: **Python 3.11+**

---

## 📌 Project Overview

Bu proje, **sıfırdan çalışan bir web crawler ve gerçek zamanlı arama motoru** inşa etmeyi hedefler. Geliştirme sürecinde birincil araç olarak **GitHub Copilot** kullanılacaktır.

Rolün artık sadece "kodlayan" değil; **AI ajanlarını yönlendiren bir Sistem Mimarı** olmaktır. Odak noktaları:

- **Mimari sağduyu** — doğru tasarım kararları vermek
- **Eşzamanlılık yönetimi** — thread'leri, kuyrukları ve paylaşılan durumu güvenli yönetmek
- **Human-in-the-Loop doğrulaması** — her AI çıktısını okumak, anlamak ve savunabilmek

Sistem iki ana bileşenden oluşur:

| Bileşen | Açıklama |
|---|---|
| **Indexer (Crawler)** | Bir seed URL'den başlayarak web'i recursive olarak tarar ve kelimeleri indexler |
| **Searcher** | Indexlenen veriyi gerçek zamanlı sorgular ve sıralı sonuçlar döndürür |

---

## 🎯 Başarı Kriterleri

| Kriter | Ağırlık | Açıklama |
|---|---|---|
| **Fonksiyonellik** | %40 | Doğru crawl ediyor ve eş zamanlı arama yapabiliyor mu? |
| **Mimari Sağduyu** | %40 | Back pressure ve thread safety ne kadar iyi yönetildi? |
| **AI Yönetimi** | %20 | AI'ın ürettiği kodu açıklayıp tasarım kararlarını savunabiliyor musun? |

---

## 📦 Teslim Edilecekler

Public bir GitHub repository içinde şunlar bulunmalıdır:

| Dosya | Açıklama |
|---|---|
| `README.md` | Bu dosya |
| `product_prd.md` | Formal Ürün Gereksinimleri Dokümanı |
| `recommendation.md` | 2 paragraflık production deployment yol haritası |
| `src/` | Tüm çalışan kaynak kodu |

---

## ⚙️ Tech Stack

| Katman | Teknoloji | Kısıt |
|---|---|---|
| **Dil** | Python 3.11+ | — |
| **HTTP İstemcisi** | `urllib.request` | ❌ `requests`, `httpx`, `aiohttp` yasak |
| **HTML Ayrıştırma** | `html.parser` (`HTMLParser`) | ❌ `BeautifulSoup`, `lxml`, `Scrapy` yasak |
| **Eşzamanlılık** | `threading`, `queue.Queue` | `threading.Lock`, `threading.RLock` kullanılacak |
| **API Sunucusu** | `http.server` / `json` | ❌ Flask, FastAPI, Django yasak |
| **Depolama** | Yerel Dosya Sistemi (`.data` dosyaları) | JSON formatında |
| **UI** | Saf HTML + JavaScript (`fetch` API) | ❌ React, Vue gibi framework yasak |
| **AI Aracı** | GitHub Copilot | Sen yönlendirirsin, Copilot yazar |

> ⚠️ **Kritik Kural:** Yalnızca Python **standart kütüphanesi** kullanılacak. Üçüncü parti HTTP veya HTML kütüphaneleri kesinlikle yasaktır.

---

## 🏗️ Sistem Mimarisi

```
┌──────────────────────────────────────────────────────────────┐
│                        TARAYICI (UI)                         │
│                                                              │
│  ┌─────────────────┐ ┌──────────────────┐ ┌───────────────┐ │
│  │  Crawler Page   │ │ Crawler Status   │ │  Search Page  │ │
│  │  (form + list)  │ │ (live log poll)  │ │ (query+results│ │
│  └────────┬────────┘ └────────┬─────────┘ └───────┬───────┘ │
└───────────┼──────────────────┼────────────────────┼─────────┘
            │  HTTP (fetch)    │  Long Polling       │
┌───────────▼──────────────────▼────────────────────▼─────────┐
│              HTTP API SERVER  (http.server / json)           │
│                                                              │
│  POST /crawl          → Yeni crawler job başlat              │
│  GET  /crawl/list     → Tüm job'ları listele                 │
│  GET  /crawl/{id}     → Job durumu + logları                 │
│  GET  /search?q=...   → Arama sorgusu                        │
│                                                              │
└──────────────┬──────────────────────────┬────────────────────┘
               │                          │
   ┌───────────▼──────────┐   ┌───────────▼──────────┐
   │   INDEXER (Crawler)  │   │  SEARCHER (Query)    │
   │                      │   │                      │
   │ threading.Thread     │   │ threading.Lock (R)   │
   │ queue.Queue (BFS)    │   │ Kelime → letter.data │
   │ threading.Lock       │   │ Frekans sıralaması   │
   │ urllib.request       │   │ Triple döndürür:     │
   │ html.parser          │   │ (url, origin, depth) │
   │ Back pressure logic  │   │ Crawler aktifken de  │
   │ Visited URL set      │   │ çalışır (live index) │
   └──────────┬───────────┘   └──────────────────────┘
              │
┌─────────────▼────────────────────────────────────────────────┐
│                    DOSYA SİSTEMİ (storage/)                  │
│                                                              │
│  visited_urls.data          → Ziyaret edilen tüm URL'ler     │
│  jobs/[crawlerid].data      → Job durumu, loglar, kuyruk     │
│  storage/a.data ... z.data  → Kelime indexi (JSON lines)     │
└──────────────────────────────────────────────────────────────┘
```

---

## 📁 Proje Klasör Yapısı

```
google-in-one-day/
│
├── src/
│   ├── crawler/
│   │   ├── __init__.py
│   │   ├── crawler.py          # Ana crawler motoru (threading.Thread)
│   │   ├── worker.py           # BFS worker — URL kuyruğunu işler
│   │   ├── fetcher.py          # urllib.request ile HTTP fetch
│   │   ├── parser.py           # html.parser ile link + kelime çıkarma
│   │   └── queue_manager.py    # Back pressure + queue.Queue yönetimi
│   │
│   ├── searcher/
│   │   ├── __init__.py
│   │   ├── search.py           # Query engine — kelime araması + sıralama
│   │   └── index_reader.py     # storage/[letter].data okuma (thread-safe)
│   │
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── file_store.py       # Dosya okuma/yazma (threading.Lock ile)
│   │   └── visited_store.py    # visited_urls.data yönetimi
│   │
│   ├── api/
│   │   ├── __init__.py
│   │   ├── server.py           # http.server tabanlı HTTP API
│   │   ├── handlers.py         # Request handler'lar
│   │   └── router.py           # URL routing mantığı
│   │
│   └── ui/
│       ├── static/
│       │   ├── index.html      # Crawler page
│       │   ├── status.html     # Crawler status page
│       │   └── search.html     # Search page
│       └── dashboard.py        # Static dosya sunucu
│
├── data/                       # Runtime verisi (gitignore'a ekle)
│   ├── visited_urls.data
│   ├── jobs/
│   │   └── [crawlerid].data
│   └── storage/
│       ├── a.data
│       ├── b.data
│       └── ...
│
├── tests/
│   ├── test_crawler.py
│   ├── test_searcher.py
│   └── test_api.py
│
├── README.md
├── product_prd.md
├── recommendation.md
├── .gitignore
└── requirements.txt            # Boş olacak — sadece stdlib kullanılıyor
```

---

## 🔧 Teknik Gereksinimler

### 🕷️ Indexer (Crawler) — Python Karşılıkları

| Gereksinim | Python Implementasyonu |
|---|---|
| **Recursive Crawling** | `queue.Queue` ile BFS; her URL `(url, depth)` tuple olarak kuyruğa girer |
| **Uniqueness** | `visited: set[str]` + `threading.Lock` — aynı URL iki kez işlenmez |
| **Back Pressure** | `queue.Queue(maxsize=N)` — kuyruk dolunca `queue.Full` exception → worker bekler |
| **Native HTTP** | `urllib.request.urlopen()` — sadece stdlib |
| **Native HTML Parse** | `html.parser.HTMLParser` subclass — link ve metin çıkarma |
| **Thread Safety** | `threading.Lock` tüm paylaşılan veri yapılarını korur |
| **Crawler ID** | `f"{int(time.time())}_{threading.current_thread().ident}"` |
| **Job Durumu** | `data/jobs/[crawlerid].data` → JSON formatında log + durum |
| **Persistence** *(Bonus)* | Job dosyasından kaldığı yerden devam etme |

**Crawler Job Yaşam Döngüsü:**

```
1. POST /crawl → url + depth parametreleri alınır
2. threading.Thread oluşturulur → crawler_id = f"{epoch}_{thread_id}"
3. data/jobs/{crawler_id}.data dosyası oluşturulur (JSON)
4. data/visited_urls.data okunur (yoksa oluşturulur)
5. BFS kuyruğuna (url, depth=0) eklenir
6. Her URL için:
   a. urllib.request ile HTML çekilir (HTTP 200 kontrolü)
   b. HTMLParser ile <a href> linkleri ve metin kelimeleri çıkarılır
   c. Kelimeler → data/storage/{ilk_harf}.data'ya yazılır
      Format: {"word": "python", "url": "...", "origin": "...", "depth": 2, "freq": 5}
   d. Yeni linkler visited kontrolünden geçer → kuyruğa eklenir
   e. Back pressure: kuyruk maxsize'a ulaşırsa worker bekler
   f. Her adım job dosyasına loglanır
7. Tüm kuyruk boşalınca job "completed" olarak işaretlenir
```

---

### 🔍 Searcher (Query Engine) — Python Karşılıkları

| Gereksinim | Python Implementasyonu |
|---|---|
| **Query Engine** | Sorguyu kelimelere böl → her kelime için `data/storage/{harf}.data` oku |
| **Sonuç Formatı** | `(relevant_url, origin_url, depth)` triple listesi |
| **Relevancy** | Frekans sayısına göre `sorted(..., key=lambda x: x['freq'], reverse=True)` |
| **Live Indexing** | `threading.RLock` ile okuma; crawler yazarken de arama çalışır |
| **Pagination** | `results[page*size:(page+1)*size]` |

---

### 🌐 API Endpoint'leri

| Method | Endpoint | Açıklama | Request Body / Params |
|---|---|---|---|
| `POST` | `/crawl` | Yeni crawler job başlat | `{"url": "...", "depth": 2, "max_queue": 100, "rate": 1.0}` |
| `GET` | `/crawl/list` | Tüm job'ları listele (zamana göre sıralı) | — |
| `GET` | `/crawl/{id}` | Job durumu + logları | `?since=0` (long polling için) |
| `GET` | `/search` | Arama sorgusu | `?q=python&page=1&size=10` |
| `GET` | `/` | Crawler page (HTML) | — |
| `GET` | `/status` | Status page (HTML) | — |
| `GET` | `/search-ui` | Search page (HTML) | — |

---

### 🖥️ UI / Dashboard Gereksinimleri

**Crawler Page (`index.html`):**
- URL input + depth input + "Crawl" butonu
- Geçmiş job listesi (zamana göre sıralı, status linki ile)
- Aktif job'lar için "running" badge

**Crawler Status Page (`status.html`):**
- Long polling ile canlı log akışı (`setInterval` + `fetch /crawl/{id}?since=N`)
- Job tamamlandı / hata bildirimi
- Metrikler: işlenen URL, kuyruk derinliği, back pressure durumu

**Search Page (`search.html`):**
- Arama kutusu + "Search" butonu
- Paginated sonuç listesi: `URL | Origin URL | Depth | Frequency`
- Crawler aktifken de çalışır

---

## 🤖 Copilot ile Çalışma Akışı

| Faz | Copilot'a Ne Söyleyeceksin |
|---|---|
| **Faz 1 — PRD** | "Bu brief'i formal bir PRD'ye genişlet: crawler + search engine projesi, Python stdlib only" |
| **Faz 2 — Mimari** | "Bu sistemi Python threading ve queue modülleri ile nasıl tasarlarım? Bana veri akışını açıkla" |
| **Faz 3 — Veri Yapıları** | "Thread-safe bir visited URL seti ve BFS kuyruğu tasarla, sadece threading.Lock ve queue.Queue kullan" |
| **Faz 4 — Crawler** | "urllib.request ve html.parser kullanarak recursive web crawler yaz, back pressure için queue.Queue(maxsize=N) kullan" |
| **Faz 5 — Search** | "data/storage/[letter].data dosyalarını thread-safe okuyan, frekansa göre sıralayan bir query engine yaz" |
| **Faz 6 — API** | "http.server.BaseHTTPRequestHandler kullanarak REST API yaz, Flask veya FastAPI kullanma" |
| **Faz 7 — UI** | "Saf HTML ve fetch API kullanarak crawler dashboard'u yaz, long polling ile canlı log akışı sağla" |

> 🧠 **Altın Kural:** Copilot'un yazdığı her fonksiyonu oku. Ne yaptığını, neden öyle yaptığını ve nasıl değiştirebileceğini açıklayabilmelisin. Kör kabul = sıfır puan.

---

## 🚀 Kurulum ve Çalıştırma

```bash
# 1. Repoyu klonla
git clone https://github.com/[kullanici-adin]/google-in-one-day.git
cd google-in-one-day

# 2. Python versiyonunu kontrol et (3.11+ gerekli)
python --version

# 3. Gerekli klasörleri oluştur
mkdir -p data/jobs data/storage

# 4. Sunucuyu başlat
python src/api/server.py

# 5. Tarayıcıda aç
# http://localhost:8080
```

> `requirements.txt` kasıtlı olarak **boştur** — bu proje yalnızca Python standart kütüphanesini kullanır.

---

---

# ✅ CHECKPOINTS

> ⚡ Her checkpoint'e geçmeden önce o aşamadaki **tüm testler geçmeli**. Bir sonraki aşamaya kırık kod ile geçilmez.

---

## 🏁 CHECKPOINT 1 — Core Crawler Engine (UI Yok, API Yok)

**Hedef:** Saf Python crawler motoru çalışıyor. Sadece CLI'dan test edilecek.

### Bu Checkpoint'te Tamamlanacaklar:

- [ ] Proje klasör yapısı oluşturuldu
- [ ] `src/storage/visited_store.py` — `visited_urls.data` oluşturma, okuma, yazma (`threading.Lock` ile)
- [ ] `src/crawler/fetcher.py` — `urllib.request.urlopen()` ile HTTP GET, HTTP 200 kontrolü, timeout yönetimi
- [ ] `src/crawler/parser.py` — `html.parser.HTMLParser` subclass: `<a href>` linkleri + sayfa metni çıkarma
- [ ] `src/storage/file_store.py` — `data/storage/[letter].data` dosyalarına JSON satırı yazma (`threading.Lock` ile)
- [ ] `src/crawler/queue_manager.py` — `queue.Queue(maxsize=N)` ile back pressure yönetimi
- [ ] `src/crawler/worker.py` — BFS worker: `(url, depth)` tuple'larını işler, derinlik kontrolü yapar
- [ ] `src/crawler/crawler.py` — `threading.Thread` ile job başlatma, crawler ID üretimi, job dosyası oluşturma
- [ ] Crawler ID formatı: `f"{int(time.time())}_{threading.current_thread().ident}"`
- [ ] `data/jobs/[crawlerid].data` — JSON formatında log ve durum yazma
- [ ] Back pressure: `queue.Queue(maxsize=100)` dolunca worker bekliyor (blocking put)
- [ ] Thread safety: `visited` set'i `threading.Lock` ile korunuyor
- [ ] Aynı URL iki kez ziyaret edilmiyor

### 🧪 Checkpoint 1 Test Komutları:

```bash
# Test 1: Basit crawl — tek derinlik
python -c "
from src.crawler.crawler import start_crawl
job_id = start_crawl('https://example.com', depth=1)
print(f'Job started: {job_id}')
import time; time.sleep(5)
"
# ✅ Beklenti: data/storage/e.data oluştu (example kelimesi için)
# ✅ Beklenti: data/visited_urls.data güncellendi
# ✅ Beklenti: data/jobs/[id].data JSON logları içeriyor

# Test 2: Derinlik sınırı kontrolü
python -c "
from src.crawler.crawler import start_crawl
import time
job_id = start_crawl('https://example.com', depth=2)
time.sleep(10)
import json
with open(f'data/jobs/{job_id}.data') as f:
    job = json.load(f)
# depth > 2 olan log satırı olmamalı
assert all(log['depth'] <= 2 for log in job['logs'] if 'depth' in log)
print('✅ Derinlik sınırı çalışıyor')
"

# Test 3: Uniqueness — aynı URL iki kez ziyaret edilmemeli
python -c "
from src.storage.visited_store import VisitedStore
store = VisitedStore()
store.add('https://example.com')
assert store.contains('https://example.com') == True
assert store.contains('https://other.com') == False
print('✅ Uniqueness çalışıyor')
"

# Test 4: Back pressure — kuyruk dolunca bloklanıyor mu?
python -c "
from src.crawler.queue_manager import QueueManager
import threading, time
qm = QueueManager(maxsize=3)
# 3 item ekle (dolmalı)
for i in range(3):
    qm.put(('https://test.com', i))
# 4. item timeout ile bloklanmalı
try:
    qm.put(('https://test.com', 4), timeout=1)
    print('❌ Back pressure çalışmıyor')
except:
    print('✅ Back pressure çalışıyor — kuyruk dolu, bekledi')
"

# Test 5: Thread safety — eş zamanlı yazma
python -c "
from src.storage.file_store import FileStore
import threading
store = FileStore()
errors = []
def write_word(i):
    try:
        store.write_word('test', f'https://url{i}.com', 'https://origin.com', 1, i)
    except Exception as e:
        errors.append(e)
threads = [threading.Thread(target=write_word, args=(i,)) for i in range(20)]
[t.start() for t in threads]
[t.join() for t in threads]
assert len(errors) == 0, f'Thread safety hatası: {errors}'
print('✅ Thread safety çalışıyor')
"

# Test 6: Fetcher — native HTTP
python -c "
from src.crawler.fetcher import fetch_page
html, status = fetch_page('https://example.com')
assert status == 200
assert '<html' in html.lower()
print(f'✅ Fetcher çalışıyor — {len(html)} karakter alındı')
"

# Test 7: Parser — link ve kelime çıkarma
python -c "
from src.crawler.parser import parse_page
html = '<html><body><a href=\"https://test.com\">Test Link</a><p>hello world</p></body></html>'
links, words = parse_page(html, base_url='https://example.com')
assert 'https://test.com' in links
assert 'hello' in words
assert 'world' in words
print(f'✅ Parser çalışıyor — {len(links)} link, {len(words)} kelime')
"
```

**✅ Checkpoint 1 Geçiş Kriteri:**
- Tüm 7 test hatasız geçiyor
- `data/storage/` altında `.data` dosyaları oluşuyor
- `data/visited_urls.data` güncelleniyor
- `data/jobs/[id].data` geçerli JSON içeriyor
- Aynı URL iki kez işlenmiyor
- Back pressure devreye giriyor

---

## 🏁 CHECKPOINT 2 — Search Engine + HTTP API

**Hedef:** Crawler çalışırken aynı anda arama yapılabiliyor. HTTP API tüm endpoint'lerde doğru yanıt veriyor.

### Bu Checkpoint'te Tamamlanacaklar:

- [ ] `src/searcher/index_reader.py` — `data/storage/[letter].data` dosyalarını `threading.RLock` ile thread-safe okuma
- [ ] `src/searcher/search.py` — sorguyu tokenize et → her kelime için ilgili `.data` dosyasını oku → frekansa göre sırala → `(url, origin_url, depth)` triple listesi döndür
- [ ] Live indexing: crawler yazarken search okuyabiliyor (RLock mekanizması)
- [ ] Pagination: `page` ve `size` parametreleri ile sonuç dilimleme
- [ ] `src/api/server.py` — `http.server.BaseHTTPRequestHandler` tabanlı HTTP sunucu
- [ ] `src/api/handlers.py` — tüm endpoint handler'ları
- [ ] `src/api/router.py` — URL routing (regex veya string matching ile)
- [ ] `POST /crawl` — yeni job başlatır, `{"crawler_id": "...", "status": "running"}` döner
- [ ] `GET /crawl/list` — tüm job'ları zamana göre sıralı listeler
- [ ] `GET /crawl/{id}` — job durumu + logları döner; `?since=N` ile long polling desteği
- [ ] `GET /search?q=...&page=1&size=10` — arama sonuçları döner
- [ ] Hata yönetimi: geçersiz URL, erişilemeyen sayfa, eksik parametre → uygun HTTP hata kodu

### 🧪 Checkpoint 2 Test Komutları:

```bash
# Sunucuyu başlat (ayrı terminal)
python src/api/server.py &
SERVER_PID=$!
sleep 2

# Test 1: Yeni crawler job başlatma
RESPONSE=$(curl -s -X POST http://localhost:8080/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "https://example.com", "depth": 1}')
echo $RESPONSE
# ✅ Beklenti: {"crawler_id": "...", "status": "running"}

CRAWLER_ID=$(echo $RESPONSE | python -c "import sys,json; print(json.load(sys.stdin)['crawler_id'])")

# Test 2: Job durumu sorgulama
sleep 3
curl -s http://localhost:8080/crawl/$CRAWLER_ID | python -m json.tool
# ✅ Beklenti: status "running" veya "completed", logs listesi mevcut

# Test 3: Job listesi
curl -s http://localhost:8080/crawl/list | python -m json.tool
# ✅ Beklenti: jobs array, zamana göre sıralı

# Test 4: Crawler bitmeden arama (live indexing testi)
curl -s "http://localhost:8080/search?q=example&page=1&size=5" | python -m json.tool
# ✅ Beklenti: results array (boş olabilir ama sistem çökmemeli)

# Test 5: Arama sonuç formatı doğrulama
sleep 5  # Crawler biraz çalışsın
RESULTS=$(curl -s "http://localhost:8080/search?q=example&page=1&size=5")
echo$RESULTS | python -c "
import sys, json
data = json.load(sys.stdin)
assert 'results' in data
assert 'total' in data
assert 'page' in data
for r in data['results']:
    assert 'url' in r
    assert 'origin_url' in r
    assert 'depth' in r
    assert 'frequency' in r
print('✅ Arama sonuç formatı doğru')
"

# Test 6: Concurrent crawler + arama (thread safety testi)
python -c "
import threading, urllib.request, json, time

def start_crawler(url):
    data = json.dumps({'url': url, 'depth': 1}).encode()
    req = urllib.request.Request('http://localhost:8080/crawl',
                                  data=data,
                                  headers={'Content-Type': 'application/json'})
    with urllib.request.urlopen(req) as r:
        return json.loads(r.read())

def search(q):
    with urllib.request.urlopen(f'http://localhost:8080/search?q={q}') as r:
        return json.loads(r.read())

# 2 crawler + 1 search eş zamanlı
threads = [
    threading.Thread(target=start_crawler, args=('https://example.com',)),
    threading.Thread(target=start_crawler, args=('https://iana.org',)),
    threading.Thread(target=search, args=('domain',)),
]
[t.start() for t in threads]
[t.join() for t in threads]
print('✅ Concurrent crawler + search — veri bozulması yok')
"

# Test 7: Hata yönetimi
curl -s -X POST http://localhost:8080/crawl \
  -H "Content-Type: application/json" \
  -d '{"url": "not-a-valid-url", "depth": 1}'
# ✅ Beklenti: HTTP 400 veya {"error": "..."} — sistem çökmemeli

# Test 8: Long polling
curl -s "http://localhost:8080/crawl/$CRAWLER_ID?since=0" | python -m json.tool
# ✅ Beklenti: since=0'dan itibaren tüm loglar

kill$SERVER_PID
```

**✅ Checkpoint 2 Geçiş Kriteri:**
- Tüm 8 test hatasız geçiyor
- API tüm endpoint'lerde doğru HTTP kodu ve JSON yanıtı veriyor
- Crawler çalışırken arama yapılabiliyor (sistem çökmüyor)
- Eş zamanlı 2 crawler + arama veri bozulmasına yol açmıyor
- Geçersiz girdiler uygun hata mesajı ile reddediliyor

---

## 🏁 CHECKPOINT 3 — Real-Time Dashboard UI + Tam Entegrasyon

**Hedef:** Sistem tamamen entegre ve kullanılabilir durumda. Dashboard canlı veri gösteriyor. Proje teslime hazır.

### Bu Checkpoint'te Tamamlanacaklar:

**UI Sayfaları:**
- [ ] `src/ui/static/index.html` — Crawler Page: form, job listesi, status linkleri
- [ ] `src/ui/static/status.html` — Crawler Status Page: canlı log akışı (long polling), metrikler
- [ ] `src/ui/static/search.html` — Search Page: arama kutusu, paginated sonuçlar
- [ ] Static dosya sunumu API server'a entegre edildi (`GET /`, `GET /status`, `GET /search-ui`)

**Dashboard Metrikleri (Gerçek Zamanlı):**
- [ ] İşlenen URL sayısı / kuyruktaki URL sayısı
- [ ] Kuyruk derinliği göstergesi
- [ ] Back pressure / throttling durumu (aktif/pasif)
- [ ] Job durumu: `running` / `completed` / `error` badge'leri

**Teslim Dosyaları:**
- [ ] `product_prd.md` tamamlandı
- [ ] `recommendation.md` tamamlandı (2 paragraf production roadmap)
- [ ] `README.md` finalize edildi
- [ ] `.gitignore` oluşturuldu (`data/` klasörü dahil)
- [ ] Kod GitHub public repository'ye push edildi

### 🧪 Checkpoint 3 Test Senaryoları:

```
# Test 1: End-to-End UI Akışı (Manuel)
─────────────────────────────────────────
1. python src/api/server.py → sunucu başladı
2. http://localhost:8080 → Crawler Page açıldı              ✅
3. URL: "https://example.com", Depth: 2 → "Crawl" tıkla
4. Job listesinde yeni job göründü (running badge)           ✅
5. "Status" linkine tıkla → status.html açıldı
6. Loglar canlı akıyor (her 2 saniyede güncelleniyor)        ✅
7. Metrikler görünüyor: işlenen URL, kuyruk derinliği        ✅
8. http://localhost:8080/search-ui → Search Page açıldı
9. "example" arama → crawler bitmeden sonuçlar geldi         ✅
10. Sonuçlar: URL | Origin URL | Depth | Frequency formatında ✅
11. Sayfa 2'ye geç → pagination çalışıyor                    ✅
12. Crawler tamamlandı → status sayfasında "completed" yazısı ✅

# Test 2: Concurrent Crawler UI Testi (Manuel)
─────────────────────────────────────────────
1. İki farklı URL için aynı anda iki crawler başlat
2. Job listesinde her ikisi de görünüyor                     ✅
3. Her birinin status sayfası bağımsız log gösteriyor        ✅
4. Birinin bitmesi diğerini etkilemiyor                      ✅

# Test 3: Back Pressure Görünürlüğü (Manuel)
─────────────────────────────────────────────
1. Büyük bir site crawl et (depth=3, max_queue=10)
2. Status sayfasında kuyruk derinliği artıyor                ✅
3. Kuyruk dolunca "Back pressure active" göstergesi çıkıyor  ✅

# Test 4: Persistence Testi - Bonus (Manuel)
─────────────────────────────────────────────
1. Crawler çalışırken Ctrl+C ile sunucuyu durdur
2. python src/api/server.py ile yeniden başlat
3. /crawl/list → önceki job'lar hâlâ listede                 ✅
4. Bonus: crawler kaldığı yerden devam ediyor                ✅

# Test 5: Fresh Clone Testi (Kritik)
─────────────────────────────────────────────
git clone [repo-url] fresh-test
cd fresh-test
mkdir -p data/jobs data/storage
python src/api/server.py
# Hiç hata olmadan başlamalı                                 ✅
# http://localhost:8080 açılmalı                             ✅
# Crawl başlatılabilmeli                                     ✅
# Arama yapılabilmeli                                        ✅

# Test 6: Teslim Kontrol Listesi
─────────────────────────────────────────────
[ ] GitHub repo public mu?
[ ] README.md mevcut ve açıklayıcı mı?
[ ] product_prd.md mevcut mi?
[ ] recommendation.md mevcut mi? (2 paragraf)
[ ] .gitignore data/ klasörünü kapsıyor mu?
[ ] requirements.txt boş mu? (stdlib only)
[ ] Tüm kod Python 3.11+ ile çalışıyor mu?
[ ] Fresh clone → run → test başarılı mı?
```

**✅ Checkpoint 3 Geçiş Kriteri:**
- Tüm UI sayfaları tarayıcıda hatasız açılıyor
- End-to-end akış (crawl → status → search) sorunsuz çalışıyor
- Tüm teslim dosyaları mevcut ve eksiksiz
- GitHub repo public ve fresh clone ile çalışıyor
- **🎉 Proje tamamlandı!**

---

## 📊 Notlandırma Hatırlatması

```
Fonksiyonellik (%40)      → Checkpoint 1 + 2 + 3 testleri
Mimari Sağduyu (%40)      → Back pressure, threading.Lock kullanımı,
                            BFS queue tasarımı, dosya yapısı kararları
AI Yönetimi (%20)         → Copilot'un yazdığı her satırı açıklayabilmek
```

---

## 🔮 Production Considerations

> Şu an implement edilmeyecek — ama `recommendation.md` için referans:

- **Storage:** Filesystem → NoSQL (crawler data) + Trie yapısı (kelime indexi) + BigQuery (analytics)
- **Scaling:** Crawler ve Search bağımsız horizontal scale; her region için izole crawler node'ları
- **Search:** PageRank algoritması, fuzzy search (yazım hatası toleransı), cümle anlama
- **Security:** Rate limiting, DDoS koruması, crawler aktivitesini gizleme, compliance
- **Monitoring:** DAU/MAU, click-through rate, crawl speed, kuyruk derinliği, node sayısı

---

## 🐍 Python Stdlib Referansı

```python
# HTTP Fetch (urllib.request)
import urllib.request
with urllib.request.urlopen(url, timeout=10) as response:
    html = response.read().decode('utf-8')
    status = response.status  # 200, 404, etc.

# HTML Parse (html.parser)
from html.parser import HTMLParser
class LinkParser(HTMLParser):
    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            for attr, val in attrs:
                if attr == 'href':
                    self.links.append(val)

# Thread-safe Queue (queue)
import queue
q = queue.Queue(maxsize=100)  # Back pressure için maxsize
q.put(item, block=True)       # Dolu ise bekler
q.get(block=True)             # Boş ise bekler

# Thread Safety (threading)
import threading
lock = threading.Lock()
rlock = threading.RLock()     # Aynı thread tekrar alabilir
with lock:
    shared_data.add(url)      # Atomik işlem

# HTTP Server (http.server)
from http.server import HTTPServer, BaseHTTPRequestHandler
class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.end_headers()
        self.wfile.write(json.dumps(data).encode())

# Crawler ID
import time, threading
crawler_id = f"{int(time.time())}_{threading.current_thread().ident}"
```

---

*Built with GitHub Copilot — Architected by a human.* 🧠🐍