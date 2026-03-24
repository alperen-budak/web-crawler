"""Tests for src/crawler/queue_manager.py — back-pressure BFS queue."""

import queue
import unittest

from src.crawler.queue_manager import QueueManager


class TestQueueManager(unittest.TestCase):
    """Unit tests for the QueueManager class."""

    def test_put_and_get(self):
        """Put an item, get it back, and verify they are equal."""
        qm = QueueManager(maxsize=10)
        item = ('https://example.com', 0)
        qm.put(item)

        result = qm.get(timeout=1)

        self.assertEqual(result, item)

    def test_maxsize_blocks_on_full(self):
        """put() with timeout should raise queue.Full when the queue is at capacity."""
        qm = QueueManager(maxsize=2)
        qm.put(('https://a.com', 0))
        qm.put(('https://b.com', 1))

        with self.assertRaises(queue.Full):
            qm.put(('https://c.com', 2), timeout=0.1)

    def test_qsize_returns_correct_count(self):
        """qsize() should reflect the number of items currently in the queue."""
        qm = QueueManager(maxsize=10)
        qm.put(('https://a.com', 0))
        qm.put(('https://b.com', 1))
        qm.put(('https://c.com', 2))

        self.assertEqual(qm.qsize(), 3)

    def test_full_returns_true_when_full(self):
        """full() should return True when the queue has reached maxsize."""
        qm = QueueManager(maxsize=2)
        qm.put(('https://a.com', 0))
        qm.put(('https://b.com', 1))

        self.assertTrue(qm.full())

    def test_full_returns_false_when_not_full(self):
        """full() should return False when the queue has available capacity."""
        qm = QueueManager(maxsize=10)

        self.assertFalse(qm.full())

    def test_fifo_order(self):
        """Items should be returned in FIFO order (first in, first out)."""
        qm = QueueManager(maxsize=10)
        items = [('https://a.com', 1), ('https://b.com', 2), ('https://c.com', 3)]
        for item in items:
            qm.put(item)

        results = [qm.get(timeout=1) for _ in range(3)]

        self.assertEqual(results, items)

    def test_empty_returns_true_for_new_queue(self):
        """A newly created queue should report as empty."""
        qm = QueueManager(maxsize=10)

        self.assertTrue(qm.empty())

    def test_empty_returns_false_after_put(self):
        """After putting an item, empty() should return False."""
        qm = QueueManager(maxsize=10)
        qm.put(('https://example.com', 0))

        self.assertFalse(qm.empty())

    def test_get_on_empty_queue_raises_timeout(self):
        """get() with timeout on an empty queue should raise queue.Empty."""
        qm = QueueManager(maxsize=10)

        with self.assertRaises(queue.Empty):
            qm.get(timeout=0.1)

    def test_maxsize_property(self):
        """The maxsize property should return the configured maximum capacity."""
        qm = QueueManager(maxsize=42)

        self.assertEqual(qm.maxsize, 42)

    def test_task_done_does_not_raise(self):
        """task_done() after a get() should not raise any exception."""
        qm = QueueManager(maxsize=10)
        qm.put(('https://example.com', 0))
        qm.get(timeout=1)

        # Should not raise
        qm.task_done()


if __name__ == '__main__':
    unittest.main()
