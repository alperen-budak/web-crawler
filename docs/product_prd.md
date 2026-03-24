# Product Requirements Document (PRD)

## Google in One Day — Python Web Crawler & Search Engine

**Version:** 1.0  
**Date:** 21 March 2026  
**Author:** AI Aided Computer Engineering Course Project  
**Language:** Python 3.11+ (stdlib only)

---

## 1. Executive Summary

This project delivers a fully functional web crawler and real-time search engine built entirely with Python's standard library. The system crawls web pages starting from a seed URL, indexes all discovered words with their frequencies, and provides a search API that returns ranked results — all while supporting concurrent operations through thread-safe data structures.

---

## 2. Problem Statement

Modern search engines are complex distributed systems, making it difficult for students to understand their fundamental mechanics. This project bridges that gap by implementing a simplified but complete search engine pipeline (crawl → index → search) using only Python stdlib, forcing deep understanding of concurrency, I/O, and data structures.

---

## 3. Goals & Non-Goals

### Goals
- Recursive BFS web crawling with configurable depth
- Real-time word indexing to filesystem-based storage
- Thread-safe concurrent crawl + search operations
- HTTP REST API for all operations (no third-party frameworks)
- Browser-based dashboard for crawl management and search
- Back pressure mechanism to prevent resource exhaustion

### Non-Goals
- Distributed crawling across multiple machines
- PageRank or advanced relevance algorithms
- Authentication or user management
- Database storage (filesystem only)
- JavaScript rendering (static HTML only)

---

## 4. System Architecture

### Components

| Component | Responsibility |
|---|---|
| **Crawler Engine** | BFS traversal, URL fetching, HTML parsing, word extraction |
| **Storage Layer** | Thread-safe file I/O for visited URLs, word index, job state |
| **Search Engine** | Query tokenization, index reading, frequency-based ranking |
| **HTTP API** | REST endpoints for crawl control and search queries |
| **Dashboard UI** | Browser interface for crawl management, live logs, search |

### Data Flow

```
Seed URL → BFS Queue → Fetch → Parse → Index Words → Storage
                ↑                  │
                └── New Links ─────┘

Search Query → Tokenize → Read Index → Rank by Frequency → Results
```

---

## 5. Functional Requirements

### 5.1 Crawler (Indexer)

| ID | Requirement | Priority |
|---|---|---|
| CR-01 | Accept a seed URL and max depth to start crawling | P0 |
| CR-02 | Use BFS with `queue.Queue` for URL traversal | P0 |
| CR-03 | Fetch pages using `urllib.request` (stdlib only) | P0 |
| CR-04 | Parse HTML using `html.parser.HTMLParser` (stdlib only) | P0 |
| CR-05 | Extract `<a href>` links and resolve relative URLs | P0 |
| CR-06 | Extract visible text words (ignore script/style) | P0 |
| CR-07 | Never visit the same URL twice (`visited` set with Lock) | P0 |
| CR-08 | Enforce back pressure via `queue.Queue(maxsize=N)` | P0 |
| CR-09 | Generate unique crawler ID: `{epoch}_{thread_ident}` | P0 |
| CR-10 | Log all operations to `data/jobs/{id}.data` (JSON) | P0 |
| CR-11 | Run in background thread (non-blocking) | P0 |
| CR-12 | Rate limiting between fetches (politeness delay) | P1 |

### 5.2 Storage

| ID | Requirement | Priority |
|---|---|---|
| ST-01 | Word index stored as JSON Lines in `data/storage/{letter}.data` | P0 |
| ST-02 | Each entry: `{word, url, origin, depth, freq}` | P0 |
| ST-03 | Visited URLs persisted in `data/visited_urls.data` | P0 |
| ST-04 | All file operations protected by `threading.Lock` | P0 |
| ST-05 | Job state persisted in `data/jobs/{id}.data` | P0 |

### 5.3 Search Engine

| ID | Requirement | Priority |
|---|---|---|
| SE-01 | Tokenize query into individual words | P0 |
| SE-02 | Read corresponding `{letter}.data` files per word | P0 |
| SE-03 | Aggregate results by URL, sum frequencies | P0 |
| SE-04 | Sort results by frequency (descending) | P0 |
| SE-05 | Support pagination (`page`, `size` params) | P0 |
| SE-06 | Case-insensitive matching | P0 |
| SE-07 | Thread-safe reading with `threading.RLock` | P0 |
| SE-08 | Work while crawler is actively writing (live index) | P0 |

### 5.4 HTTP API

| ID | Endpoint | Method | Priority |
|---|---|---|---|
| AP-01 | `/crawl` | POST | P0 |
| AP-02 | `/crawl/list` | GET | P0 |
| AP-03 | `/crawl/{id}` | GET | P0 |
| AP-04 | `/search?q=...&page=N&size=N` | GET | P0 |
| AP-05 | `/` (Crawler Page) | GET | P0 |
| AP-06 | `/status` (Status Page) | GET | P0 |
| AP-07 | `/search-ui` (Search Page) | GET | P0 |

### 5.5 Dashboard UI

| ID | Requirement | Priority |
|---|---|---|
| UI-01 | Crawler form: URL input, depth input, submit button | P0 |
| UI-02 | Job list with status badges (running/completed/error) | P0 |
| UI-03 | Live log view with long polling (`setInterval` + `fetch`) | P0 |
| UI-04 | Real-time metrics: processed URLs, queue size, errors | P0 |
| UI-05 | Back pressure indicator | P1 |
| UI-06 | Search page with paginated results table | P0 |
| UI-07 | Frequency bar visualization | P2 |

---

## 6. Non-Functional Requirements

| Requirement | Target |
|---|---|
| Language | Python 3.11+ |
| Dependencies | stdlib only — no pip packages |
| Concurrency | `threading` + `queue.Queue` |
| HTTP | `http.server` + `urllib.request` |
| HTML Parsing | `html.parser.HTMLParser` |
| Thread Safety | `threading.Lock` for writes, `threading.RLock` for reads |
| Port | 8080 (configurable via `PORT` env var) |
| Storage | Local filesystem, JSON format |
| Browser Support | Any modern browser with `fetch()` API |

---

## 7. Constraints

- **No third-party HTTP libraries:** `requests`, `httpx`, `aiohttp` are forbidden
- **No third-party HTML parsers:** `BeautifulSoup`, `lxml`, `Scrapy` are forbidden
- **No web frameworks:** Flask, FastAPI, Django are forbidden
- **No frontend frameworks:** React, Vue, Angular are forbidden
- **No databases:** SQLite, PostgreSQL, Redis are forbidden
- Only Python standard library modules are permitted

---

## 8. Success Metrics

| Metric | Target |
|---|---|
| Functional correctness | All checkpoint tests pass |
| Thread safety | No data corruption under concurrent access |
| Back pressure | Queue blocks when full, no memory overflow |
| Live indexing | Search works while crawler is active |
| Error handling | No server crashes on invalid input |
| Test coverage | 79+ unit/integration tests passing |
