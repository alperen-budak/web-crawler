"""Tests for src/api/ — HTTP API server, router, and handlers."""

import json
import os
import socket
import tempfile
import threading
import time
import unittest
import urllib.error
import urllib.request

from src.api.router import Router
from src.storage import database


class TestRouter(unittest.TestCase):
    """Unit tests for the URL Router."""

    def test_get_route_matches(self):
        """GET routes should match correctly."""
        router = Router()
        handler = lambda h, **kw: None
        router.get('/search', handler)

        found, params = router.resolve('GET', '/search?q=test')
        self.assertIs(found, handler)
        self.assertEqual(params, {})

    def test_post_route_matches(self):
        """POST routes should match correctly."""
        router = Router()
        handler = lambda h, **kw: None
        router.post('/crawl', handler)

        found, params = router.resolve('POST', '/crawl')
        self.assertIs(found, handler)

    def test_path_params_extracted(self):
        """Path parameters like /crawl/{id} should be extracted."""
        router = Router()
        handler = lambda h, **kw: None
        router.get('/crawl/{id}', handler)

        found, params = router.resolve('GET', '/crawl/12345_6789')
        self.assertIs(found, handler)
        self.assertEqual(params, {'id': '12345_6789'})

    def test_no_match_returns_none(self):
        """Unmatched paths should return (None, {})."""
        router = Router()
        router.get('/search', lambda h, **kw: None)

        found, params = router.resolve('GET', '/unknown')
        self.assertIsNone(found)

    def test_method_mismatch_returns_none(self):
        """Wrong HTTP method should not match."""
        router = Router()
        router.get('/crawl', lambda h, **kw: None)

        found, params = router.resolve('POST', '/crawl')
        self.assertIsNone(found)

    def test_list_before_param_route(self):
        """/crawl/list should match before /crawl/{id}."""
        router = Router()
        list_handler = lambda h, **kw: 'list'
        id_handler = lambda h, **kw: 'id'
        router.get('/crawl/list', list_handler)
        router.get('/crawl/{id}', id_handler)

        found, _ = router.resolve('GET', '/crawl/list')
        self.assertIs(found, list_handler)

        found, params = router.resolve('GET', '/crawl/some_id')
        self.assertIs(found, id_handler)
        self.assertEqual(params, {'id': 'some_id'})


def _get_free_port() -> int:
    """Find and return a free TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]


class TestAPIEndpoints(unittest.TestCase):
    """Integration tests for the HTTP API endpoints."""

    @classmethod
    def setUpClass(cls):
        """Start the API server on a random free port with a temp SQLite DB."""
        cls._tmpdir = tempfile.TemporaryDirectory()
        cls._db_path = os.path.join(cls._tmpdir.name, 'test.db')
        database.close_db()
        database.init_db(cls._db_path)

        # Start server on a free port
        cls._port = _get_free_port()
        cls._base_url = f'http://localhost:{cls._port}'

        from http.server import HTTPServer
        from src.api.server import APIRequestHandler
        cls._server = HTTPServer(('localhost', cls._port), APIRequestHandler)
        cls._thread = threading.Thread(target=cls._server.serve_forever, daemon=True)
        cls._thread.start()
        time.sleep(0.3)  # Let the server start

    @classmethod
    def tearDownClass(cls):
        """Shut down the server and clean up."""
        cls._server.shutdown()
        cls._server.server_close()
        # Wait for any crawler threads to finish
        time.sleep(1)
        database.close_db()
        cls._tmpdir.cleanup()

    def _request(self, method: str, path: str, body: dict | None = None,
                 expect_status: int | None = None) -> tuple[dict, int]:
        """Helper to make an HTTP request and return (parsed_json, status_code)."""
        url = f'{self._base_url}{path}'
        data = json.dumps(body).encode('utf-8') if body else None
        req = urllib.request.Request(url, data=data, method=method)
        if data:
            req.add_header('Content-Type', 'application/json')

        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                raw = resp.read().decode('utf-8')
                status = resp.status
                result = json.loads(raw) if raw else {}
        except urllib.error.HTTPError as e:
            raw = e.read().decode('utf-8')
            status = e.code
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = {'raw': raw}

        if expect_status is not None:
            self.assertEqual(status, expect_status,
                             f'Expected {expect_status}, got {status}: {result}')
        return result, status

    # ─── POST /crawl ──────────────────────────────────────────────

    def test_post_crawl_starts_job(self):
        """POST /crawl with valid URL should return 201 with crawler_id and status."""
        data, status = self._request('POST', '/crawl',
                                     body={'url': 'https://example.com', 'depth': 1},
                                     expect_status=201)
        self.assertIn('crawler_id', data)
        self.assertEqual(data['status'], 'running')

    def test_post_crawl_missing_url(self):
        """POST /crawl without url field should return 400."""
        data, status = self._request('POST', '/crawl', body={'depth': 1})
        self.assertEqual(status, 400)
        self.assertIn('error', data)

    def test_post_crawl_invalid_url(self):
        """POST /crawl with non-http URL should return 400."""
        data, status = self._request('POST', '/crawl',
                                     body={'url': 'not-a-valid-url', 'depth': 1})
        self.assertEqual(status, 400)
        self.assertIn('error', data)

    def test_post_crawl_empty_body(self):
        """POST /crawl with empty body should return 400."""
        url = f'{self._base_url}/crawl'
        req = urllib.request.Request(url, data=b'', method='POST')
        req.add_header('Content-Type', 'application/json')
        req.add_header('Content-Length', '0')
        try:
            with urllib.request.urlopen(req, timeout=5) as resp:
                status = resp.status
        except urllib.error.HTTPError as e:
            status = e.code
        self.assertEqual(status, 400)

    # ─── GET /crawl/list ──────────────────────────────────────────

    def test_get_crawl_list(self):
        """GET /crawl/list should return a list of jobs."""
        data, status = self._request('GET', '/crawl/list', expect_status=200)
        self.assertIn('jobs', data)
        self.assertIsInstance(data['jobs'], list)

    # ─── GET /crawl/{id} ─────────────────────────────────────────

    def test_get_crawl_status_existing(self):
        """GET /crawl/{id} for an active job should return job data."""
        # Start a job first
        create_data, _ = self._request('POST', '/crawl',
                                       body={'url': 'https://example.com', 'depth': 1})
        cid = create_data['crawler_id']
        time.sleep(1)  # Let the job file be created

        data, status = self._request('GET', f'/crawl/{cid}', expect_status=200)
        self.assertIn('status', data)
        self.assertIn('logs', data)

    def test_get_crawl_status_not_found(self):
        """GET /crawl/{id} for a non-existent job should return 404."""
        data, status = self._request('GET', '/crawl/nonexistent_99999')
        self.assertEqual(status, 404)
        self.assertIn('error', data)

    def test_get_crawl_status_long_polling(self):
        """GET /crawl/{id}?since=0 should return logs from offset 0."""
        create_data, _ = self._request('POST', '/crawl',
                                       body={'url': 'https://example.com', 'depth': 1})
        cid = create_data['crawler_id']
        time.sleep(2)

        data, status = self._request('GET', f'/crawl/{cid}?since=0', expect_status=200)
        self.assertIn('logs', data)
        self.assertIn('log_offset', data)
        self.assertIn('total_logs', data)

    # ─── GET /search ──────────────────────────────────────────────

    def test_search_returns_results_format(self):
        """GET /search?q=... should return results with correct structure."""
        # Pre-populate some data via the database
        database.insert_word('example', 'https://example.com', 'https://example.com', 0, 10)

        data, status = self._request('GET', '/search?q=example&page=1&size=5',
                                     expect_status=200)
        self.assertIn('results', data)
        self.assertIn('total', data)
        self.assertIn('page', data)

    def test_search_empty_query(self):
        """GET /search without q parameter should return 400."""
        data, status = self._request('GET', '/search')
        self.assertEqual(status, 400)

    def test_search_query_alias(self):
        """GET /search?query=... should work as alias for q=..."""
        database.insert_word('aliasword', 'https://alias.com', 'https://alias.com', 0, 3)

        data, status = self._request('GET', '/search?query=aliasword',
                                     expect_status=200)
        self.assertIn('results', data)
        self.assertGreater(len(data['results']), 0)

    def test_search_no_crash_on_unknown_word(self):
        """GET /search for a word with no results should return empty list, not crash."""
        data, status = self._request('GET', '/search?q=zzznomatch', expect_status=200)
        self.assertEqual(data['results'], [])
        self.assertEqual(data['total'], 0)

    # ─── 404 ──────────────────────────────────────────────────────

    def test_unknown_path_returns_404(self):
        """Requesting an unregistered path should return 404."""
        data, status = self._request('GET', '/unknown/path')
        self.assertEqual(status, 404)

    # ─── CORS ─────────────────────────────────────────────────────

    def test_options_preflight(self):
        """OPTIONS request should return 204 with CORS headers."""
        url = f'{self._base_url}/crawl'
        req = urllib.request.Request(url, method='OPTIONS')
        with urllib.request.urlopen(req, timeout=5) as resp:
            self.assertEqual(resp.status, 204)


if __name__ == '__main__':
    unittest.main()
