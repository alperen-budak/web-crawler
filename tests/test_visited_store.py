"""Tests for src/storage/visited_store.py — thread-safe visited URL store (SQLite-backed)."""

import os
import tempfile
import threading
import unittest

from src.storage import database
from src.storage.visited_store import VisitedStore


class TestVisitedStore(unittest.TestCase):
    """Unit tests for the VisitedStore class."""

    def setUp(self):
        """Create a fresh temporary SQLite database for each test."""
        self._tmpdir = tempfile.TemporaryDirectory()
        self._db_path = os.path.join(self._tmpdir.name, 'test.db')
        database.close_db()
        database.init_db(self._db_path)

    def tearDown(self):
        """Close the database and clean up."""
        database.close_db()
        self._tmpdir.cleanup()

    def _make_store(self) -> VisitedStore:
        """Helper to create a VisitedStore with a test crawler_id."""
        return VisitedStore(crawler_id='test_job_1')

    def test_add_and_contains(self):
        """Adding a URL should make contains() return True for that URL."""
        store = self._make_store()
        store.add('https://example.com')

        self.assertTrue(store.contains('https://example.com'))

    def test_contains_returns_false_for_unknown_url(self):
        """contains() should return False for a URL that was never added."""
        store = self._make_store()

        self.assertFalse(store.contains('https://unknown.com'))

    def test_no_duplicate_entries(self):
        """Adding the same URL twice should not create duplicates."""
        store = self._make_store()
        first_add = store.add('https://example.com')
        second_add = store.add('https://example.com')

        # First add returns True (new), second returns False (duplicate)
        self.assertTrue(first_add)
        self.assertFalse(second_add)

        # Count should be 1
        self.assertEqual(store.count(), 1)

    def test_persists_in_database(self):
        """URLs should survive across VisitedStore instances (same crawler_id, same DB)."""
        store1 = self._make_store()
        store1.add('https://example.com')
        store1.add('https://python.org')

        # Create a brand new instance with the same crawler_id
        store2 = self._make_store()

        self.assertTrue(store2.contains('https://example.com'))
        self.assertTrue(store2.contains('https://python.org'))

    def test_thread_safe_concurrent_adds(self):
        """50 threads adding unique URLs concurrently should not raise exceptions."""
        store = self._make_store()
        errors = []
        num_threads = 50

        def add_url(i):
            try:
                store.add(f'https://example.com/page/{i}')
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_url, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f'Thread safety errors: {errors}')
        self.assertEqual(store.count(), num_threads)
        for i in range(num_threads):
            self.assertTrue(store.contains(f'https://example.com/page/{i}'))

    def test_count_returns_correct_number(self):
        """count() should reflect the number of unique URLs added."""
        store = self._make_store()
        self.assertEqual(store.count(), 0)

        store.add('https://a.com')
        store.add('https://b.com')
        store.add('https://c.com')

        self.assertEqual(store.count(), 3)

    def test_get_all_returns_sorted_list(self):
        """get_all() should return all URLs sorted alphabetically."""
        store = self._make_store()
        store.add('https://c.com')
        store.add('https://a.com')
        store.add('https://b.com')

        all_urls = store.get_all()

        self.assertEqual(all_urls, [
            'https://a.com',
            'https://b.com',
            'https://c.com',
        ])


if __name__ == '__main__':
    unittest.main()

