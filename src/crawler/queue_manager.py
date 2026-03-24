"""
queue_manager.py — Back-pressure aware BFS queue manager.

Uses queue.Queue(maxsize=N) to enforce back pressure.
When the queue is full, put() blocks until space is available.
"""

import queue


class QueueManager:
    """
    Thread-safe BFS queue with back pressure support.

    Wraps queue.Queue(maxsize=N).  When the queue reaches maxsize,
    put() will block (or raise queue.Full if a timeout is given).
    """

    def __init__(self, maxsize: int = 100):
        """
        Args:
            maxsize: Maximum queue capacity. 0 means unlimited.
        """
        self._queue: queue.Queue[tuple[str, int]] = queue.Queue(maxsize=maxsize)
        self._maxsize = maxsize

    def put(self, item: tuple[str, int], timeout: float | None = None) -> None:
        """
        Add a (url, depth) tuple to the queue.

        Args:
            item: Tuple of (url, depth).
            timeout: If given, block for at most this many seconds.
                     Raises queue.Full if the queue is still full after timeout.
                     If None, blocks indefinitely until space is available.
        """
        if timeout is not None:
            self._queue.put(item, block=True, timeout=timeout)
        else:
            self._queue.put(item, block=True)

    def get(self, timeout: float | None = None) -> tuple[str, int]:
        """
        Remove and return a (url, depth) tuple from the queue.

        Args:
            timeout: If given, block for at most this many seconds.
                     Raises queue.Empty if the queue is still empty after timeout.
                     If None, blocks indefinitely until an item is available.

        Returns:
            A (url, depth) tuple.
        """
        if timeout is not None:
            return self._queue.get(block=True, timeout=timeout)
        else:
            return self._queue.get(block=True)

    def task_done(self) -> None:
        """Signal that a previously dequeued task is complete."""
        self._queue.task_done()

    def empty(self) -> bool:
        """Return True if the queue is empty (approximate)."""
        return self._queue.empty()

    def full(self) -> bool:
        """Return True if the queue is full (approximate)."""
        return self._queue.full()

    def qsize(self) -> int:
        """Return the approximate number of items in the queue."""
        return self._queue.qsize()

    @property
    def maxsize(self) -> int:
        """Return the maximum queue capacity."""
        return self._maxsize
