"""Tests for src/storage/file_store.py — thread-safe word index storage (SQLite-backed)."""

import os
import tempfile
import threading
import unittest

from src.storage import database
from src.storage.file_store import FileStore


class TestFileStore(unittest.TestCase):
    """Unit tests for the FileStore class."""

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

    def _make_store(self) -> FileStore:
        """Helper to create a FileStore."""
        return FileStore()

    def test_write_word_stores_entry(self):
        """Calling write_word() should store an entry that can be read back."""
        store = self._make_store()
        store.write_word('python', 'https://example.com', 'https://origin.com', 1, 3)

        entries = store.read_words('p')
        self.assertEqual(len(entries), 1)

    def test_write_word_correct_format(self):
        """The stored entry should have the correct keys and values."""
        store = self._make_store()
        store.write_word('python', 'https://example.com', 'https://origin.com', 2, 5)

        entries = store.read_words('p')
        entry = entries[0]
        self.assertEqual(entry['word'], 'python')
        self.assertEqual(entry['url'], 'https://example.com')
        self.assertEqual(entry['origin'], 'https://origin.com')
        self.assertEqual(entry['depth'], 2)
        self.assertEqual(entry['freq'], 5)

    def test_write_word_appends_multiple_entries(self):
        """Multiple write_word() calls for same-letter words should all be stored."""
        store = self._make_store()
        store.write_word('python', 'https://a.com', 'https://origin.com', 1, 1)
        store.write_word('programming', 'https://b.com', 'https://origin.com', 1, 2)
        store.write_word('parser', 'https://c.com', 'https://origin.com', 1, 3)

        entries = store.read_words('p')
        self.assertEqual(len(entries), 3)

    def test_write_word_uses_first_letter(self):
        """write_word('apple', ...) should be readable via read_words('a')."""
        store = self._make_store()
        store.write_word('apple', 'https://example.com', 'https://origin.com', 0, 1)

        a_entries = store.read_words('a')
        self.assertEqual(len(a_entries), 1)
        self.assertEqual(a_entries[0]['word'], 'apple')

    def test_thread_safe_concurrent_writes(self):
        """50 threads writing unique words concurrently should produce no errors or corruption."""
        store = self._make_store()
        errors = []
        num_threads = 50

        def write_word(i):
            try:
                store.write_word(
                    f'test{i}', f'https://url{i}.com', 'https://origin.com', 1, i
                )
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=write_word, args=(i,)) for i in range(num_threads)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f'Thread safety errors: {errors}')

        # All 50 words start with 't', so read_words('t') should have them all
        entries = store.read_words('t')
        self.assertEqual(len(entries), num_threads)
        for entry in entries:
            self.assertIn('word', entry)

    def test_write_words_batch(self):
        """write_words_batch() should write all entries efficiently."""
        store = self._make_store()
        entries = [
            {'word': 'alpha', 'url': 'https://a.com', 'origin': 'https://o.com', 'depth': 0, 'freq': 2},
            {'word': 'beta', 'url': 'https://b.com', 'origin': 'https://o.com', 'depth': 1, 'freq': 3},
            {'word': 'apple', 'url': 'https://c.com', 'origin': 'https://o.com', 'depth': 0, 'freq': 1},
        ]
        store.write_words_batch(entries)

        # 'a' letter should have 2 entries (alpha, apple), 'b' should have 1 (beta)
        a_entries = store.read_words('a')
        b_entries = store.read_words('b')

        self.assertEqual(len(a_entries), 2)
        self.assertEqual(len(b_entries), 1)

    def test_read_words_returns_empty_for_missing_letter(self):
        """Reading a letter with no entries should return an empty list."""
        store = self._make_store()

        result = store.read_words('z')

        self.assertEqual(result, [])

    def test_non_alpha_words_go_to_underscore(self):
        """Words starting with a digit or special char should be retrievable via '_'."""
        store = self._make_store()
        store.write_word('42answer', 'https://example.com', 'https://o.com', 0, 1)

        entries = store.read_words('_')
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0]['word'], '42answer')


if __name__ == '__main__':
    unittest.main()

