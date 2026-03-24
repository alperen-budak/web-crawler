"""
database.py — Centralized SQLite storage for the crawler.

Provides a thread-safe, singleton database connection using WAL mode.
All persistent data (word index, visited URLs, jobs, logs) stored in
a single lightweight SQLite database at data/crawler.db.

sqlite3 is part of Python stdlib — no third-party packages required.

Tables
------
words        : Indexed word entries   (replaces JSON Lines .data files)
visited_urls : Per-job visited URLs   (replaces per-job visited .data files)
jobs         : Crawler job metadata   (replaces per-job JSON job files)
job_logs     : Per-job log entries    (for live log streaming)
"""

import json
import os
import sqlite3
import threading

# Default database path
DB_PATH = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..', 'data', 'crawler.db')
)

_lock = threading.Lock()        # protects singleton init
_write_lock = threading.Lock()  # serializes all write operations
_conn: sqlite3.Connection | None = None


# ─── Connection Management ────────────────────────────────────────

def get_connection(db_path: str | None = None) -> sqlite3.Connection:
    """
    Get or create the singleton SQLite connection.

    Uses WAL mode for concurrent read/write and busy_timeout to
    avoid 'database is locked' errors under contention.
    check_same_thread=False allows the connection to be shared
    across the main thread and crawler worker threads.
    """
    global _conn
    if _conn is not None:
        return _conn
    with _lock:
        if _conn is not None:
            return _conn
        path = db_path or DB_PATH
        os.makedirs(os.path.dirname(path), exist_ok=True)
        _conn = sqlite3.connect(path, check_same_thread=False)
        _conn.execute("PRAGMA journal_mode=WAL")
        _conn.execute("PRAGMA busy_timeout=5000")
        _conn.row_factory = sqlite3.Row
        _init_tables(_conn)
        return _conn


def init_db(db_path: str | None = None) -> sqlite3.Connection:
    """
    (Re-)initialize the database with a specific path.
    Closes any existing connection first. Used by tests.
    """
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None
    return get_connection(db_path)


def close_db() -> None:
    """Close the singleton connection and reset. Used by tests."""
    global _conn
    with _lock:
        if _conn is not None:
            try:
                _conn.close()
            except Exception:
                pass
            _conn = None


def _init_tables(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they don't exist."""
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS words (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            word TEXT NOT NULL,
            url TEXT NOT NULL,
            origin TEXT NOT NULL,
            depth INTEGER NOT NULL,
            freq INTEGER NOT NULL,
            crawler_id TEXT NOT NULL DEFAULT ''
        );
        CREATE INDEX IF NOT EXISTS idx_words_word ON words(word);

        CREATE TABLE IF NOT EXISTS visited_urls (
            url TEXT NOT NULL,
            crawler_id TEXT NOT NULL,
            PRIMARY KEY (url, crawler_id)
        );

        CREATE TABLE IF NOT EXISTS jobs (
            crawler_id TEXT PRIMARY KEY,
            status TEXT NOT NULL DEFAULT 'running',
            max_depth INTEGER NOT NULL DEFAULT 2,
            processed INTEGER NOT NULL DEFAULT 0,
            errors INTEGER NOT NULL DEFAULT 0,
            queue_size INTEGER NOT NULL DEFAULT 0,
            created_at REAL NOT NULL,
            seed_url TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS job_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            crawler_id TEXT NOT NULL,
            log_json TEXT NOT NULL
        );
        CREATE INDEX IF NOT EXISTS idx_logs_crawler ON job_logs(crawler_id);
    """)
    conn.commit()
    _migrate(conn)
    _mark_stale_jobs(conn)


def _migrate(conn: sqlite3.Connection) -> None:
    """Run lightweight schema migrations for existing databases."""
    # Add seed_url column if missing (added after initial schema)
    try:
        conn.execute("SELECT seed_url FROM jobs LIMIT 0")
    except sqlite3.OperationalError:
        conn.execute("ALTER TABLE jobs ADD COLUMN seed_url TEXT NOT NULL DEFAULT ''")
        conn.commit()


def _mark_stale_jobs(conn: sqlite3.Connection) -> None:
    """Mark jobs left in 'running' state from a previous process as 'failed'."""
    with _write_lock:
        conn.execute(
            "UPDATE jobs SET status = 'failed' WHERE status = 'running'"
        )
        conn.commit()


# ─── Word Index Operations ────────────────────────────────────────

def insert_word(word: str, url: str, origin: str, depth: int, freq: int,
                crawler_id: str = '') -> None:
    """Insert a single word entry into the words table."""
    conn = get_connection()
    with _write_lock:
        conn.execute(
            "INSERT INTO words (word, url, origin, depth, freq, crawler_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (word.lower(), url, origin, depth, freq, crawler_id)
        )
        conn.commit()


def insert_words_batch(entries: list[dict], crawler_id: str = '') -> None:
    """Insert multiple word entries in a single transaction."""
    if not entries:
        return
    conn = get_connection()
    rows = [
        (e['word'].lower(), e['url'], e.get('origin', ''),
         e.get('depth', 0), e.get('freq', 0), crawler_id)
        for e in entries
    ]
    with _write_lock:
        conn.executemany(
            "INSERT INTO words (word, url, origin, depth, freq, crawler_id) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            rows
        )
        conn.commit()


def read_words_by_letter(letter: str) -> list[dict]:
    """Read all word entries whose first character matches *letter*."""
    conn = get_connection()
    letter = letter.lower()
    if letter == '_':
        # Non-alphabetic first character
        rows = conn.execute(
            "SELECT word, url, origin, depth, freq FROM words "
            "WHERE SUBSTR(word, 1, 1) NOT BETWEEN 'a' AND 'z'"
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT word, url, origin, depth, freq FROM words "
            "WHERE SUBSTR(word, 1, 1) = ?",
            (letter,)
        ).fetchall()
    return [dict(r) for r in rows]


def read_words_by_word(word: str) -> list[dict]:
    """Read all entries for a specific word (exact match, case-insensitive)."""
    if not word:
        return []
    conn = get_connection()
    rows = conn.execute(
        "SELECT word, url, origin, depth, freq FROM words WHERE word = ?",
        (word.lower(),)
    ).fetchall()
    return [dict(r) for r in rows]


# ─── Data File Export ─────────────────────────────────────────────

def export_words_to_data_files(data_dir: str | None = None) -> None:
    """
    Export all word entries from SQLite to JSON Lines .data files.

    Creates data/storage/[letter].data files matching the original
    file-based storage format. Each line is a JSON object:
        {"word": "...", "url": "...", "origin": "...", "depth": N, "freq": N}

    Non-alphabetic words go to _.data.
    """
    if data_dir is None:
        data_dir = os.path.join(os.path.dirname(DB_PATH), 'storage')
    os.makedirs(data_dir, exist_ok=True)

    conn = get_connection()
    rows = conn.execute(
        "SELECT word, url, origin, depth, freq FROM words ORDER BY word"
    ).fetchall()

    # Group entries by first letter
    files: dict[str, list[str]] = {}
    for r in rows:
        entry = dict(r)
        first_char = entry['word'][0].lower() if entry['word'] else '_'
        if not first_char.isalpha():
            first_char = '_'
        if first_char not in files:
            files[first_char] = []
        files[first_char].append(json.dumps(entry, ensure_ascii=False))

    # Write each letter file
    for letter, lines in files.items():
        filepath = os.path.join(data_dir, f'{letter}.data')
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write('\n'.join(lines) + '\n')


# ─── Visited URL Operations ──────────────────────────────────────

def add_visited(url: str, crawler_id: str) -> bool:
    """
    Mark a URL as visited for a specific crawler job.
    Returns True if newly added, False if already visited.
    Uses INSERT OR IGNORE + rowcount to detect duplicates atomically.
    """
    conn = get_connection()
    with _write_lock:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO visited_urls (url, crawler_id) VALUES (?, ?)",
            (url, crawler_id)
        )
        conn.commit()
        return cursor.rowcount > 0


def add_visited_batch(urls: list[str], crawler_id: str) -> list[str]:
    """
    Mark multiple URLs as visited in a single transaction.
    Returns the list of URLs that were *newly* added (not previously visited).
    Much faster than calling add_visited() in a loop (one commit vs N commits).
    """
    if not urls:
        return []
    conn = get_connection()
    newly_added: list[str] = []
    with _write_lock:
        for url in urls:
            cursor = conn.execute(
                "INSERT OR IGNORE INTO visited_urls (url, crawler_id) VALUES (?, ?)",
                (url, crawler_id)
            )
            if cursor.rowcount > 0:
                newly_added.append(url)
        conn.commit()
    return newly_added


def is_visited(url: str, crawler_id: str) -> bool:
    """Check whether a URL has been visited for a given crawler job."""
    conn = get_connection()
    row = conn.execute(
        "SELECT 1 FROM visited_urls WHERE url = ? AND crawler_id = ?",
        (url, crawler_id)
    ).fetchone()
    return row is not None


def count_visited(crawler_id: str) -> int:
    """Count visited URLs for a specific crawler job."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM visited_urls WHERE crawler_id = ?",
        (crawler_id,)
    ).fetchone()
    return row[0]


def get_all_visited(crawler_id: str) -> list[str]:
    """Get all visited URLs for a specific crawler job, sorted."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT url FROM visited_urls WHERE crawler_id = ? ORDER BY url",
        (crawler_id,)
    ).fetchall()
    return [r[0] for r in rows]


# ─── Job Operations ──────────────────────────────────────────────

def create_job(crawler_id: str, max_depth: int, created_at: float,
               seed_url: str = '') -> None:
    """Create a new crawler job record."""
    conn = get_connection()
    with _write_lock:
        conn.execute(
            "INSERT OR REPLACE INTO jobs "
            "(crawler_id, status, max_depth, processed, errors, queue_size, created_at, seed_url) "
            "VALUES (?, 'running', ?, 0, 0, 0, ?, ?)",
            (crawler_id, max_depth, created_at, seed_url)
        )
        conn.commit()


def update_job(crawler_id: str, **kwargs) -> None:
    """
    Update specific fields of a job.
    Accepts keyword arguments matching column names:
        status, processed, errors, queue_size
    """
    allowed = {'status', 'processed', 'errors', 'queue_size'}
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    if not filtered:
        return
    conn = get_connection()
    sets = ', '.join(f"{k} = ?" for k in filtered)
    values = list(filtered.values()) + [crawler_id]
    with _write_lock:
        conn.execute(f"UPDATE jobs SET {sets} WHERE crawler_id = ?", values)
        conn.commit()


def add_job_log(crawler_id: str, log_entry: dict) -> None:
    """Append a log entry (stored as JSON text) to a job."""
    conn = get_connection()
    with _write_lock:
        conn.execute(
            "INSERT INTO job_logs (crawler_id, log_json) VALUES (?, ?)",
            (crawler_id, json.dumps(log_entry, ensure_ascii=False))
        )
        conn.commit()


def add_log_and_update_job(crawler_id: str, log_entry: dict,
                           status: str | None = None,
                           processed: int | None = None,
                           errors: int | None = None,
                           queue_size: int | None = None) -> None:
    """
    Append a log entry AND update job metadata in a single transaction.
    Avoids two separate lock acquisitions + two commits per log event.
    """
    conn = get_connection()
    with _write_lock:
        conn.execute(
            "INSERT INTO job_logs (crawler_id, log_json) VALUES (?, ?)",
            (crawler_id, json.dumps(log_entry, ensure_ascii=False))
        )
        updates = {}
        if status is not None:
            updates['status'] = status
        if processed is not None:
            updates['processed'] = processed
        if errors is not None:
            updates['errors'] = errors
        if queue_size is not None:
            updates['queue_size'] = queue_size
        if updates:
            sets = ', '.join(f"{k} = ?" for k in updates)
            values = list(updates.values()) + [crawler_id]
            conn.execute(f"UPDATE jobs SET {sets} WHERE crawler_id = ?", values)
        conn.commit()


def get_job(crawler_id: str) -> dict | None:
    """Get job metadata by crawler_id. Returns None if not found."""
    conn = get_connection()
    row = conn.execute(
        "SELECT crawler_id, status, max_depth, processed, errors, queue_size, created_at, seed_url "
        "FROM jobs WHERE crawler_id = ?",
        (crawler_id,)
    ).fetchone()
    if row is None:
        return None
    return dict(row)


def get_job_logs(crawler_id: str, since: int = 0) -> list[dict]:
    """
    Get log entries for a job.
    *since* is an offset — logs with rownum > since are returned.
    """
    conn = get_connection()
    rows = conn.execute(
        "SELECT log_json FROM job_logs WHERE crawler_id = ? "
        "ORDER BY id LIMIT -1 OFFSET ?",
        (crawler_id, since)
    ).fetchall()
    result = []
    for r in rows:
        try:
            result.append(json.loads(r[0]))
        except json.JSONDecodeError:
            pass
    return result


def count_job_logs(crawler_id: str) -> int:
    """Count total log entries for a job."""
    conn = get_connection()
    row = conn.execute(
        "SELECT COUNT(*) FROM job_logs WHERE crawler_id = ?",
        (crawler_id,)
    ).fetchone()
    return row[0]


def list_all_jobs() -> list[dict]:
    """List all jobs sorted by creation time (newest first)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT crawler_id, status, max_depth, processed, errors, queue_size, created_at, seed_url "
        "FROM jobs ORDER BY created_at DESC"
    ).fetchall()
    return [dict(r) for r in rows]
