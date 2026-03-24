"""Tests for src/searcher/search.py — query engine (SQLite-backed)."""

import os
import tempfile
import unittest

from src.storage import database
from src.searcher.search import search


class TestSearch(unittest.TestCase):
    """Unit tests for the search function."""

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

    def _write_record(self, word: str, url: str, origin: str, depth: int, freq: int):
        """Helper to insert a test word record into the database."""
        database.insert_word(word, url, origin, depth, freq)

    def test_search_returns_results_for_known_word(self):
        """Searching for a word that exists in the index should return non-empty results."""
        self._write_record('python', 'https://python.org', 'https://origin.com', 1, 10)

        result = search('python', page=1, size=10)

        self.assertIsInstance(result, dict)
        self.assertGreater(len(result['results']), 0)

    def test_search_result_has_correct_keys(self):
        """Each result dict should have keys: url, origin_url, depth, frequency, relevance_score."""
        self._write_record('python', 'https://python.org', 'https://origin.com', 1, 5)

        result = search('python', page=1, size=10)

        for r in result['results']:
            self.assertIn('url', r)
            self.assertIn('origin_url', r)
            self.assertIn('depth', r)
            self.assertIn('frequency', r)
            self.assertIn('relevance_score', r)

    def test_search_sorted_by_frequency(self):
        """Results sorted by frequency should be in descending order."""
        self._write_record('python', 'https://a.com', 'https://o.com', 1, 1)
        self._write_record('python', 'https://b.com', 'https://o.com', 1, 5)
        self._write_record('python', 'https://c.com', 'https://o.com', 1, 2)

        result = search('python', page=1, size=10, sort_by='frequency')

        frequencies = [r['frequency'] for r in result['results']]
        self.assertEqual(frequencies, sorted(frequencies, reverse=True))
        self.assertEqual(frequencies, [5, 2, 1])

    def test_search_sorted_by_relevance(self):
        """Default sort by relevance should use the score formula."""
        # depth=0, freq=5 → score = 50 + 1000 - 0 = 1050
        self._write_record('python', 'https://a.com', 'https://o.com', 0, 5)
        # depth=2, freq=20 → score = 200 + 1000 - 10 = 1190
        self._write_record('python', 'https://b.com', 'https://o.com', 2, 20)
        # depth=1, freq=1 → score = 10 + 1000 - 5 = 1005
        self._write_record('python', 'https://c.com', 'https://o.com', 1, 1)

        result = search('python', page=1, size=10, sort_by='relevance')

        scores = [r['relevance_score'] for r in result['results']]
        self.assertEqual(scores, [1190, 1050, 1005])

    def test_relevance_score_formula(self):
        """relevance_score should equal (freq*10) + 1000 - (depth*5)."""
        self._write_record('python', 'https://x.com', 'https://o.com', 3, 7)

        result = search('python', page=1, size=10)
        r = result['results'][0]

        expected = (7 * 10) + 1000 - (3 * 5)  # 70 + 1000 - 15 = 1055
        self.assertEqual(r['relevance_score'], expected)

    def test_search_pagination(self):
        """Pagination should return correct slices of results."""
        # Write 15 records with unique URLs
        for i in range(15):
            self._write_record('python', f'https://site{i}.com', 'https://o.com', 1, 15 - i)

        page1 = search('python', page=1, size=5)
        page2 = search('python', page=2, size=5)

        self.assertEqual(len(page1['results']), 5)
        self.assertEqual(len(page2['results']), 5)
        self.assertEqual(page1['total'], 15)
        self.assertEqual(page2['total'], 15)

        # Pages should contain different URLs
        urls_page1 = {r['url'] for r in page1['results']}
        urls_page2 = {r['url'] for r in page2['results']}
        self.assertEqual(len(urls_page1 & urls_page2), 0,
                         'Page 1 and Page 2 should have no overlapping URLs')

    def test_search_returns_empty_for_unknown_word(self):
        """Searching for a word not in the index should return empty results."""
        result = search('zzznomatch', page=1, size=10)

        self.assertEqual(result['results'], [])
        self.assertEqual(result['total'], 0)

    def test_search_is_case_insensitive(self):
        """Search should be case-insensitive — 'Python' and 'python' should match."""
        self._write_record('python', 'https://python.org', 'https://o.com', 1, 3)

        result = search('Python', page=1, size=10)

        self.assertGreater(len(result['results']), 0)

    def test_search_multi_word_query(self):
        """A multi-word query should return results matching any of the words."""
        self._write_record('python', 'https://python.org', 'https://o.com', 1, 5)
        self._write_record('crawler', 'https://crawler.io', 'https://o.com', 1, 3)

        result = search('python crawler', page=1, size=10)

        urls = {r['url'] for r in result['results']}
        self.assertIn('https://python.org', urls)
        self.assertIn('https://crawler.io', urls)

    def test_search_returns_page_number(self):
        """The response dict should include the current page number."""
        result = search('anything', page=3, size=10)

        self.assertEqual(result['page'], 3)

    def test_search_empty_query(self):
        """An empty query string should return empty results without crashing."""
        result = search('', page=1, size=10)

        self.assertEqual(result['results'], [])
        self.assertEqual(result['total'], 0)

    def test_search_aggregates_same_url(self):
        """Multiple entries for the same URL should have their frequencies summed."""
        self._write_record('python', 'https://example.com', 'https://o.com', 1, 3)
        self._write_record('python', 'https://example.com', 'https://o.com', 1, 2)

        result = search('python', page=1, size=10)

        # Should be aggregated into one result with freq 5
        self.assertEqual(len(result['results']), 1)
        self.assertEqual(result['results'][0]['frequency'], 5)


if __name__ == '__main__':
    unittest.main()

