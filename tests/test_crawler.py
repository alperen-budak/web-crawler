"""Tests for src/crawler/crawler.py — main crawler engine (SQLite-backed)."""

import os
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from src.storage import database
from src.crawler.crawler import start_crawl


class TestCrawler(unittest.TestCase):
    """Unit tests for the start_crawl function and crawler lifecycle."""

    def setUp(self):
        """Create a fresh temp SQLite database so real data/ is never touched."""
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._tmpdir.name, 'test.db')
        database.close_db()
        database.init_db(self._db_path)

        # Track threads that exist before each test
        self._threads_before = set(threading.enumerate())

    def _wait_for_crawler_threads(self, timeout: float = 5.0):
        """Wait for any crawler threads spawned during the test to finish."""
        deadline = time.time() + timeout
        for t in threading.enumerate():
            if t not in self._threads_before and t is not threading.current_thread():
                remaining = deadline - time.time()
                if remaining > 0:
                    t.join(timeout=remaining)

    def tearDown(self):
        """Wait for crawler threads, close DB, and clean up."""
        self._wait_for_crawler_threads()
        database.close_db()
        self._tmpdir.cleanup()

    @patch('src.crawler.worker.fetch_page')
    def test_start_crawl_returns_crawler_id(self, mock_fetch):
        """start_crawl() should return a non-empty string crawler_id."""
        mock_fetch.return_value = ('<html><body>Hello</body></html>', 200)

        crawler_id = start_crawl('https://example.com', depth=1, rate=0)

        self.assertIsInstance(crawler_id, str)
        self.assertTrue(len(crawler_id) > 0)

    @patch('src.crawler.worker.fetch_page')
    def test_crawler_id_format(self, mock_fetch):
        """crawler_id should match the format: digits_digits (epoch_threadident)."""
        mock_fetch.return_value = ('<html><body>Hello</body></html>', 200)

        crawler_id = start_crawl('https://example.com', depth=1, rate=0)

        # Format: epoch_threadident — both parts are numeric
        self.assertEqual(crawler_id.count('_'), 1,
                         f'crawler_id "{crawler_id}" should contain exactly one underscore')
        parts = crawler_id.split('_')
        self.assertTrue(parts[0].isdigit(),
                        f'First part "{parts[0]}" should be numeric (epoch)')
        self.assertTrue(parts[1].isdigit(),
                        f'Second part "{parts[1]}" should be numeric (thread ident)')

    @patch('src.crawler.worker.fetch_page')
    def test_job_is_created_in_db(self, mock_fetch):
        """After start_crawl(), a job record should exist in the database."""
        mock_fetch.return_value = ('<html><body>Hello</body></html>', 200)

        crawler_id = start_crawl('https://example.com', depth=1, rate=0)
        time.sleep(1)  # Give thread time to create the record

        job = database.get_job(crawler_id)
        self.assertIsNotNone(job, 'Job record should exist in the database')

    @patch('src.crawler.worker.fetch_page')
    def test_job_has_valid_data(self, mock_fetch):
        """The job record should contain valid data with expected keys."""
        mock_fetch.return_value = ('<html><body>Hello</body></html>', 200)

        crawler_id = start_crawl('https://example.com', depth=1, rate=0)
        time.sleep(2)  # Wait for crawl to process

        job = database.get_job(crawler_id)
        self.assertIn('status', job)
        self.assertIn('crawler_id', job)
        self.assertIn('max_depth', job)

        logs = database.get_job_logs(crawler_id)
        self.assertIsInstance(logs, list)
        self.assertGreater(len(logs), 0)

    @patch('src.crawler.worker.fetch_page')
    def test_visited_urls_in_db(self, mock_fetch):
        """The seed URL should appear in visited_urls after starting a crawl."""
        mock_fetch.return_value = ('<html><body>Hello</body></html>', 200)

        crawler_id = start_crawl('https://example.com', depth=1, rate=0)
        time.sleep(1)

        visited = database.get_all_visited(crawler_id)
        self.assertIn('https://example.com', visited)

    @patch('src.crawler.worker.fetch_page')
    def test_depth_limit_respected(self, mock_fetch):
        """No URL at depth > max_depth should be fetched."""
        html_with_links = (
            '<html><body>'
            '<a href="https://example.com/a">A</a>'
            '<a href="https://example.com/b">B</a>'
            '<p>test content</p>'
            '</body></html>'
        )
        mock_fetch.return_value = (html_with_links, 200)

        crawler_id = start_crawl('https://example.com', depth=1, rate=0)
        time.sleep(3)  # Give enough time for the crawl to finish

        logs = database.get_job_logs(crawler_id)
        for log in logs:
            if 'depth' in log:
                self.assertLessEqual(log['depth'], 1,
                                     f'Found log with depth {log["depth"]} > max_depth 1')


if __name__ == '__main__':
    unittest.main()

