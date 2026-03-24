"""Tests for src/crawler/fetcher.py — HTTP page fetcher."""

import io
import socket
import unittest
import urllib.error
import urllib.request
from email.message import EmailMessage
from unittest.mock import MagicMock, patch

from src.crawler.fetcher import fetch_page


class _FakeResponse(io.BytesIO):
    """Minimal fake response object that mimics urllib response."""

    def __init__(self, data: bytes, status: int = 200,
                 content_type: str = 'text/html; charset=utf-8'):
        super().__init__(data)
        self.status = status
        self.headers = EmailMessage()
        self.headers['Content-Type'] = content_type

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()


class TestFetcher(unittest.TestCase):
    """Unit tests for the fetch_page function."""

    @patch('src.crawler.fetcher.urllib.request.urlopen')
    def test_fetch_returns_200_for_valid_url(self, mock_urlopen):
        """Fetching a valid URL should return (html_string, 200)."""
        html_bytes = b'<html><body>Hello</body></html>'
        mock_urlopen.return_value = _FakeResponse(html_bytes, status=200)

        html, status = fetch_page('https://example.com')

        self.assertEqual(status, 200)
        self.assertIn('Hello', html)
        self.assertIsInstance(html, str)

    @patch('src.crawler.fetcher.urllib.request.urlopen')
    def test_fetch_returns_error_status_for_bad_url(self, mock_urlopen):
        """Fetching a URL that returns 404 should return (message, 404) without crashing."""
        mock_urlopen.side_effect = urllib.error.HTTPError(
            url='https://example.com/missing',
            code=404,
            msg='Not Found',
            hdrs=EmailMessage(),
            fp=io.BytesIO(b''),
        )

        html, status = fetch_page('https://example.com/missing')

        self.assertEqual(status, 404)
        # Should not crash — returns some string (error description)
        self.assertIsInstance(html, str)

    @patch('src.crawler.fetcher.urllib.request.urlopen')
    def test_fetch_handles_timeout(self, mock_urlopen):
        """A socket timeout should be handled gracefully, returning ('...', 0)."""
        mock_urlopen.side_effect = urllib.error.URLError(reason=socket.timeout('timed out'))

        html, status = fetch_page('https://example.com')

        self.assertEqual(status, 0)
        self.assertIsInstance(html, str)

    @patch('src.crawler.fetcher.urllib.request.urlopen')
    def test_fetch_decodes_html_as_utf8(self, mock_urlopen):
        """The returned HTML should be a decoded str, not bytes."""
        html_bytes = '<html><body>Türkçe içerik</body></html>'.encode('utf-8')
        mock_urlopen.return_value = _FakeResponse(html_bytes, status=200)

        html, status = fetch_page('https://example.com')

        self.assertEqual(status, 200)
        self.assertIsInstance(html, str)
        self.assertNotIsInstance(html, bytes)
        self.assertIn('Türkçe', html)

    @patch('src.crawler.fetcher.urllib.request.urlopen')
    def test_fetch_handles_connection_refused(self, mock_urlopen):
        """A connection refused error should return a safe default."""
        mock_urlopen.side_effect = urllib.error.URLError(
            reason=ConnectionRefusedError('Connection refused')
        )

        html, status = fetch_page('https://localhost:9999')

        self.assertEqual(status, 0)
        self.assertIsInstance(html, str)

    @patch('src.crawler.fetcher.urllib.request.urlopen')
    def test_fetch_returns_empty_for_non_html_content(self, mock_urlopen):
        """Non-HTML content types should return empty string with status code."""
        mock_urlopen.return_value = _FakeResponse(
            b'\x89PNG\r\n', status=200, content_type='image/png'
        )

        html, status = fetch_page('https://example.com/image.png')

        self.assertEqual(status, 200)
        self.assertEqual(html, '')


if __name__ == '__main__':
    unittest.main()
