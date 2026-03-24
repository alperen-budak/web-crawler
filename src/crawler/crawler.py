"""
crawler.py — Main crawler engine.

Starts a new crawl job in a background thread:
  1. Generates a unique crawler_id
  2. Creates the job record in SQLite
  3. Creates the BFS queue and seeds it with the start URL
  4. Launches a threading.Thread running the BFS worker
  5. Returns the crawler_id immediately

Crawler ID format: "{epoch}_{thread_ident}"
"""

import threading
import time

from src.crawler.queue_manager import QueueManager
from src.crawler.worker import BFSWorker
from src.storage.file_store import FileStore
from src.storage.visited_store import VisitedStore
from src.storage import database

# Global registry of active crawler jobs (crawler_id → BFSWorker)
_active_jobs: dict[str, BFSWorker] = {}
_jobs_lock = threading.Lock()


def start_crawl(
    url: str,
    depth: int = 2,
    max_queue: int = 100,
    rate: float = 1.0,
) -> str:
    """
    Start a new crawl job in a background thread.

    Args:
        url: Seed URL to start crawling from.
        depth: Maximum crawl depth (default 2).
        max_queue: Maximum BFS queue size for back pressure (default 100).
        rate: Seconds between consecutive fetches (default 1.0).

    Returns:
        The unique crawler_id string.
    """
    epoch = int(time.time())

    # Container for the real ID and a signal for the main thread
    id_holder: list[str | None] = [None]
    id_ready = threading.Event()

    def _thread_target() -> None:
        """Set up everything with the real thread ident, then run the worker."""
        real_id = f"{epoch}_{threading.current_thread().ident}"
        id_holder[0] = real_id

        # Create job record in the database
        database.create_job(real_id, max_depth=depth, created_at=float(epoch),
                            seed_url=url)

        # Per-job visited store (isolated by crawler_id in SQLite)
        visited_store = VisitedStore(crawler_id=real_id)
        file_store = FileStore()
        queue_manager = QueueManager(maxsize=max_queue)

        worker = BFSWorker(
            crawler_id=real_id,
            queue_manager=queue_manager,
            visited_store=visited_store,
            file_store=file_store,
            max_depth=depth,
            rate=rate,
        )

        # Seed the queue
        visited_store.add(url)
        queue_manager.put((url, 0))

        # Register in the global registry
        with _jobs_lock:
            _active_jobs[real_id] = worker

        # Signal: ID is ready, main thread can return
        id_ready.set()

        worker.run()

    thread = threading.Thread(target=_thread_target, daemon=True)
    thread.start()
    id_ready.wait(timeout=5)

    real_id = id_holder[0] or f"{epoch}_{thread.ident}"

    # Also register from the parent side (belt-and-suspenders)
    with _jobs_lock:
        if real_id not in _active_jobs:
            _active_jobs[real_id] = None  # type: ignore

    return real_id


def get_job(crawler_id: str) -> BFSWorker | None:
    """Get a crawler job by its ID."""
    with _jobs_lock:
        return _active_jobs.get(crawler_id)


def list_jobs() -> list[str]:
    """Return all known crawler IDs."""
    with _jobs_lock:
        return list(_active_jobs.keys())

        return list(_active_jobs.keys())
