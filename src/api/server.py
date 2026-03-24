"""
server.py — HTTP API server using http.server (stdlib).

Binds to port 8080 (or PORT env var) and routes requests
through the Router to the appropriate handler.

No Flask, FastAPI, or Django — pure stdlib.
"""

import os
import sys
import json
from http.server import HTTPServer, BaseHTTPRequestHandler

# Ensure project root is on sys.path so imports work
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.api.router import Router
from src.api.handlers import (
    handle_crawl_start,
    handle_crawl_list,
    handle_crawl_status,
    handle_search,
)

# ─── Static file serving ─────────────────────────────────────────

STATIC_DIR = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', 'ui', 'static')
)

MIME_TYPES = {
    '.html': 'text/html; charset=utf-8',
    '.css': 'text/css; charset=utf-8',
    '.js': 'application/javascript; charset=utf-8',
    '.json': 'application/json; charset=utf-8',
    '.png': 'image/png',
    '.ico': 'image/x-icon',
}


def _serve_static(handler, filename: str) -> None:
    """Serve a static file from the ui/static directory."""
    filepath = os.path.join(STATIC_DIR, filename)
    if not os.path.isfile(filepath):
        handler.send_response(404)
        handler.send_header('Content-Type', 'text/plain')
        handler.end_headers()
        handler.wfile.write(b'404 Not Found')
        return

    ext = os.path.splitext(filename)[1].lower()
    mime = MIME_TYPES.get(ext, 'application/octet-stream')

    with open(filepath, 'rb') as f:
        content = f.read()

    handler.send_response(200)
    handler.send_header('Content-Type', mime)
    handler.send_header('Content-Length', str(len(content)))
    handler.end_headers()
    handler.wfile.write(content)


# Static page handlers
def handle_index(handler, **kwargs):
    """GET / → Crawler Page (index.html)"""
    _serve_static(handler, 'index.html')

def handle_status_page(handler, **kwargs):
    """GET /status → Status Page (status.html)"""
    _serve_static(handler, 'status.html')

def handle_search_ui(handler, **kwargs):
    """GET /search-ui → Search Page (search.html)"""
    _serve_static(handler, 'search.html')


# ─── Router setup ─────────────────────────────────────────────────

router = Router()

# API endpoints
router.post('/crawl', handle_crawl_start)
router.get('/crawl/list', handle_crawl_list)
router.get('/crawl/{id}', handle_crawl_status)
router.get('/search', handle_search)

# Static pages
router.get('/', handle_index)
router.get('/status', handle_status_page)
router.get('/search-ui', handle_search_ui)


# ─── Request Handler ──────────────────────────────────────────────

class APIRequestHandler(BaseHTTPRequestHandler):
    """HTTP request handler that delegates to the router."""

    def do_GET(self):
        self._dispatch('GET')

    def do_POST(self):
        self._dispatch('POST')

    def do_OPTIONS(self):
        """Handle CORS preflight requests."""
        self.send_response(204)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()

    def _dispatch(self, method: str):
        """Route the request to the appropriate handler."""
        handler_func, params = router.resolve(method, self.path)
        if handler_func:
            try:
                handler_func(self, **params)
            except Exception as e:
                self.send_response(500)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                error_body = json.dumps({'error': f'Internal server error: {str(e)}'})
                self.wfile.write(error_body.encode('utf-8'))
        else:
            self.send_response(404)
            self.send_header('Content-Type', 'application/json')
            self.end_headers()
            body = json.dumps({'error': f'Not found: {method} {self.path}'})
            self.wfile.write(body.encode('utf-8'))

    def log_message(self, format, *args):
        """Override to use a cleaner log format."""
        sys.stderr.write(f"[API] {self.address_string()} - {format % args}\n")


# ─── Server entry point ──────────────────────────────────────────

def run_server(host: str = '0.0.0.0', port: int = 8080):
    """Start the HTTP server."""
    # Initialize the SQLite database
    from src.storage.database import get_connection
    get_connection()

    server = HTTPServer((host, port), APIRequestHandler)
    print(f'🚀 Server running at http://{host}:{port}')
    print(f'   Crawler Page:  http://localhost:{port}/')
    print(f'   Status Page:   http://localhost:{port}/status')
    print(f'   Search Page:   http://localhost:{port}/search-ui')
    print(f'   API:           http://localhost:{port}/crawl, /search')
    print(f'   Press Ctrl+C to stop.')

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print('\n🛑 Server stopped.')
        server.server_close()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    run_server(port=port)
