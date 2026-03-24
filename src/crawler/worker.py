"""
worker.py — BFS worker that processes (url, depth) tuples from the queue.

For each URL:
  1. Fetch the HTML page via fetcher.py
  2. Parse links and words via parser.py
  3. Write word index entries via file_store.py
  4. Add new (unseen) links to the queue (if depth < max_depth)
  5. Log each step to the SQLite database
"""

import queue
import time
import threading
from collections import Counter

from src.crawler.fetcher import fetch_page
from src.crawler.parser import parse_page
from src.crawler.queue_manager import QueueManager
from src.storage.file_store import FileStore
from src.storage.visited_store import VisitedStore
from src.storage import database
from src.storage.database import add_log_and_update_job, export_words_to_data_files


class BFSWorker:
    """
    BFS crawl worker.

    Consumes (url, depth) tuples from a QueueManager,
    fetches and parses pages, indexes words, and discovers new links.
    """

    def __init__(
        self,
        crawler_id: str,
        queue_manager: QueueManager,
        visited_store: VisitedStore,
        file_store: FileStore,
        max_depth: int,
        rate: float = 1.0,
    ):
        """
        Args:
            crawler_id: Unique job identifier.
            queue_manager: BFS queue to consume from.
            visited_store: Thread-safe visited URL set.
            file_store: Thread-safe word index storage.
            max_depth: Maximum crawl depth.
            rate: Minimum seconds between consecutive fetches (politeness).
        """
        self.crawler_id = crawler_id
        self.queue_manager = queue_manager
        self.visited_store = visited_store
        self.file_store = file_store
        self.max_depth = max_depth
        self.rate = rate

        self._processed_count = 0
        self._error_count = 0
        self._status = 'running'
        self._stop_event = threading.Event()

    def _add_log(self, log_entry: dict) -> None:
        """Append a log entry and update job metadata in one transaction."""
        add_log_and_update_job(
            self.crawler_id,
            log_entry,
            status=self._status,
            processed=self._processed_count,
            errors=self._error_count,
            queue_size=self.queue_manager.qsize(),
        )

    def stop(self) -> None:
        """Signal the worker to stop after current URL."""
        self._stop_event.set()

    def run(self) -> None:
        """
        Main BFS loop. Runs until queue is empty or stop is requested.
        """
        while not self._stop_event.is_set():
            try:
                url, depth = self.queue_manager.get(timeout=3)
            except queue.Empty:
                # Queue is empty — crawl is done
                break

            try:
                self._process_url(url, depth)
            except Exception as e:
                self._error_count += 1
                self._add_log({
                    'type': 'error',
                    'url': url,
                    'depth': depth,
                    'message': str(e),
                    'timestamp': time.time(),
                })
            finally:
                self.queue_manager.task_done()

            # Rate limiting (politeness delay)
            if self.rate > 0:
                time.sleep(self.rate)

        # Mark job as completed
        self._status = 'completed'
        self._add_log({
            'type': 'status',
            'message': 'Crawl completed',
            'processed': self._processed_count,
            'errors': self._error_count,
            'timestamp': time.time(),
        })

        # Export word index to .data files for raw file access
        try:
            export_words_to_data_files()
        except Exception:
            pass  # Best-effort export; DB is the source of truth

    def _process_url(self, url: str, depth: int) -> None:
        """Fetch, parse, index words, and enqueue new links for a single URL."""

        self._add_log({
            'type': 'fetch',
            'url': url,
            'depth': depth,
            'timestamp': time.time(),
        })

        # 1. Fetch
        html, status = fetch_page(url)
        if status != 200 or not html:
            self._error_count += 1
            self._add_log({
                'type': 'fetch_error',
                'url': url,
                'depth': depth,
                'status': status,
                'timestamp': time.time(),
            })
            return

        self._add_log({
            'type': 'fetched',
            'url': url,
            'depth': depth,
            'status': status,
            'size': len(html),
            'timestamp': time.time(),
        })

        # 2. Parse
        links, words = parse_page(html, base_url=url)

        # 3. Index words — count frequencies on this page
        word_freq = Counter(words)
        entries = []
        for word, freq in word_freq.items():
            entries.append({
                'word': word,
                'url': url,
                'origin': url,
                'depth': depth,
                'freq': freq,
            })
        if entries:
            self.file_store.write_words_batch(entries)

        self._processed_count += 1
        self._add_log({
            'type': 'indexed',
            'url': url,
            'depth': depth,
            'words': len(word_freq),
            'links_found': len(links),
            'timestamp': time.time(),
        })

        # 4. Enqueue new links if within depth limit
        if depth < self.max_depth:
            # Batch-mark all links as visited in ONE transaction
            # (previously did N individual commits — the main bottleneck)
            new_urls = self.visited_store.add_batch(links)

            new_links_count = 0
            dropped_count = 0
            for link in new_urls:
                if self.queue_manager.full():
                    # Queue is full — count all remaining links as dropped
                    dropped_count += len(new_urls) - new_links_count - dropped_count
                    break
                try:
                    # Non-blocking put: if queue is full, skip immediately
                    self.queue_manager.put((link, depth + 1), timeout=0)
                    new_links_count += 1
                except queue.Full:
                    dropped_count += 1

            if dropped_count > 0:
                self._add_log({
                    'type': 'back_pressure',
                    'depth': depth + 1,
                    'message': f'Queue full — {dropped_count} links dropped',
                    'timestamp': time.time(),
                })

            if new_links_count > 0:
                self._add_log({
                    'type': 'enqueued',
                    'depth': depth + 1,
                    'new_links': new_links_count,
                    'queue_size': self.queue_manager.qsize(),
                    'timestamp': time.time(),
                })

