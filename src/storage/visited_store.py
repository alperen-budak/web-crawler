"""
visited_store.py — Thread-safe visited URL store backed by SQLite.

Each crawler job has its own isolated set of visited URLs,
identified by crawler_id. Delegates persistence to database.py.
"""

from src.storage.database import (
    get_connection,
    add_visited,
    add_visited_batch,
    is_visited,
    count_visited,
    get_all_visited,
)


class VisitedStore:
    """Thread-safe set of visited URLs backed by SQLite."""

    def __init__(self, crawler_id: str = '', **kwargs):
        """
        Args:
            crawler_id: Unique job identifier — isolates visited sets per job.
            **kwargs: Accepts (and ignores) legacy 'filepath' parameter.
        """
        self._crawler_id = crawler_id
        get_connection()  # ensure DB is initialized

    def add(self, url: str) -> bool:
        """
        Add a URL to the visited set.
        Returns True if the URL was newly added, False if already present.
        """
        return add_visited(url, self._crawler_id)

    def add_batch(self, urls: list[str]) -> list[str]:
        """
        Add multiple URLs to the visited set in a single transaction.
        Returns the list of URLs that were newly added.
        """
        return add_visited_batch(urls, self._crawler_id)

    def contains(self, url: str) -> bool:
        """Check whether a URL has been visited."""
        return is_visited(url, self._crawler_id)

    def count(self) -> int:
        """Return the number of visited URLs."""
        return count_visited(self._crawler_id)

    def get_all(self) -> list[str]:
        """Return a sorted copy of all visited URLs."""
        return get_all_visited(self._crawler_id)

