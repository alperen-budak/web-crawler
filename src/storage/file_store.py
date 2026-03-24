"""
file_store.py — Thread-safe word index storage backed by SQLite.

Delegates all persistence to database.py.
Keeps the same public API so callers (worker.py) don't change.
"""

from src.storage.database import (
    get_connection,
    insert_word,
    insert_words_batch,
    read_words_by_letter,
)


class FileStore:
    """Thread-safe word index storage backed by SQLite."""

    def __init__(self, data_dir: str | None = None):
        # data_dir kept for backward compat (ignored — DB handles path)
        get_connection()  # ensure DB is initialized

    def write_word(self, word: str, url: str, origin: str, depth: int, freq: int) -> None:
        """Write a single word entry to the database."""
        insert_word(word, url, origin, depth, freq)

    def write_words_batch(self, entries: list[dict]) -> None:
        """Write multiple word entries in one transaction."""
        insert_words_batch(entries)

    def read_words(self, letter: str) -> list[dict]:
        """Read all word entries starting with a given letter."""
        return read_words_by_letter(letter)

