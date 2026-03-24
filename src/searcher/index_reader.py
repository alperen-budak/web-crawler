"""
index_reader.py — Thread-safe reader for the word index, backed by SQLite.

Delegates all reads to database.py. The RLock is no longer needed
because SQLite WAL mode handles concurrent reads natively.
"""

from src.storage.database import (
    get_connection,
    read_words_by_letter,
    read_words_by_word,
)


class IndexReader:
    """Thread-safe reader for the word index (SQLite-backed)."""

    def __init__(self, data_dir: str | None = None):
        # data_dir kept for backward compat (ignored)
        get_connection()  # ensure DB is initialized

    def read(self, letter: str) -> list[dict]:
        """
        Read all word entries whose first character matches *letter*.

        Args:
            letter: Single character (a-z) or '_' for non-alpha.

        Returns:
            List of dicts with keys: word, url, origin, depth, freq.
        """
        return read_words_by_letter(letter)

    def read_word(self, word: str) -> list[dict]:
        """
        Read all entries for a specific word.

        Args:
            word: The word to search for.

        Returns:
            List of matching entry dicts.
        """
        return read_words_by_word(word)

