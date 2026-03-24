"""
handlers.py — Request handlers for all API endpoints.

Each handler receives the BaseHTTPRequestHandler instance and optional
path parameters, reads the request, and writes the response.
"""

import json
from urllib.parse import urlparse, parse_qs

from src.crawler.crawler import start_crawl
from src.searcher.search import search
from src.storage import database


def _send_json(handler, data: dict, status: int = 200) -> None:
    """Helper: send a JSON response."""
    body = json.dumps(data, ensure_ascii=False, indent=2).encode('utf-8')
    handler.send_response(status)
    handler.send_header('Content-Type', 'application/json; charset=utf-8')
    handler.send_header('Access-Control-Allow-Origin', '*')
    handler.send_header('Content-Length', str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def _send_error(handler, message: str, status: int = 400) -> None:
    """Helper: send a JSON error response."""
    _send_json(handler, {'error': message}, status=status)


def _parse_query(handler) -> dict:
    """Parse query string parameters from the request path."""
    parsed = urlparse(handler.path)
    return {k: v[0] if len(v) == 1 else v for k, v in parse_qs(parsed.query).items()}


def _read_body(handler) -> bytes:
    """Read the request body."""
    content_length = int(handler.headers.get('Content-Length', 0))
    if content_length > 0:
        return handler.rfile.read(content_length)
    return b''


# ─── POST /crawl ────────────────────────────────────────────────

def handle_crawl_start(handler, **kwargs) -> None:
    """
    POST /crawl — Start a new crawler job.

    Request body: {"url": "...", "depth": 2, "max_queue": 100, "rate": 1.0}
    Response:     {"crawler_id": "...", "status": "running"}
    """
    try:
        raw = _read_body(handler)
        if not raw:
            _send_error(handler, 'Request body is required', 400)
            return
        body = json.loads(raw.decode('utf-8'))
    except (json.JSONDecodeError, UnicodeDecodeError):
        _send_error(handler, 'Invalid JSON in request body', 400)
        return

    url = body.get('url', '').strip()
    if not url:
        _send_error(handler, 'Missing required field: url', 400)
        return

    # Basic URL validation
    if not url.startswith(('http://', 'https://')):
        _send_error(handler, 'Invalid URL: must start with http:// or https://', 400)
        return

    depth = body.get('depth', 2)
    max_queue = body.get('max_queue', 100)
    rate = body.get('rate', 1.0)

    # Validate numeric params
    try:
        depth = int(depth)
        max_queue = int(max_queue)
        rate = float(rate)
    except (ValueError, TypeError):
        _send_error(handler, 'depth, max_queue must be integers; rate must be a number', 400)
        return

    if depth < 0 or depth > 10:
        _send_error(handler, 'depth must be between 0 and 10', 400)
        return

    crawler_id = start_crawl(url=url, depth=depth, max_queue=max_queue, rate=rate)

    _send_json(handler, {
        'crawler_id': crawler_id,
        'status': 'running',
    }, status=201)


# ─── GET /crawl/list ─────────────────────────────────────────────

def handle_crawl_list(handler, **kwargs) -> None:
    """
    GET /crawl/list — List all crawler jobs sorted by time (newest first).

    Response: {"jobs": [{"crawler_id": "...", "status": "...", ...}, ...]}
    """
    jobs = database.list_all_jobs()
    _send_json(handler, {'jobs': jobs})


# ─── GET /crawl/{id} ─────────────────────────────────────────────

def handle_crawl_status(handler, id: str = '', **kwargs) -> None:
    """
    GET /crawl/{id} — Get job status and logs.

    Query params: ?since=N (return logs with index >= N for long polling)
    Response:     Job metadata + logs.
    """
    job = database.get_job(id)
    if job is None:
        _send_error(handler, f'Job not found: {id}', 404)
        return

    result = dict(job)

    # Long polling: ?since=N filters logs to offset >= N
    query = _parse_query(handler)
    since = query.get('since')
    since_idx = 0
    if since is not None:
        try:
            since_idx = int(since)
        except (ValueError, TypeError):
            pass

    logs = database.get_job_logs(id, since=since_idx)
    total_logs = database.count_job_logs(id)

    result['logs'] = logs
    if since is not None:
        result['log_offset'] = since_idx
        result['total_logs'] = total_logs

    _send_json(handler, result)


# ─── GET /search ──────────────────────────────────────────────────

def handle_search(handler, **kwargs) -> None:
    """
    GET /search?q=...&page=1&size=10&sortBy=relevance — Search the word index.

    Also accepts 'query' as alias for 'q'.
    sortBy: 'relevance' (default) or 'frequency'.
    Response: {"results": [...], "total": N, "page": N}
    """
    query = _parse_query(handler)
    q = query.get('q', query.get('query', '')).strip()

    if not q:
        _send_error(handler, 'Missing required query parameter: q or query', 400)
        return

    try:
        page = int(query.get('page', 1))
        size = int(query.get('size', 10))
    except (ValueError, TypeError):
        _send_error(handler, 'page and size must be integers', 400)
        return

    if page < 1:
        page = 1
    if size < 1 or size > 100:
        size = 10

    sort_by = query.get('sortBy', 'relevance')
    if sort_by not in ('relevance', 'frequency'):
        sort_by = 'relevance'

    results = search(query=q, page=page, size=size, sort_by=sort_by)
    _send_json(handler, results)
