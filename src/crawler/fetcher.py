"""
fetcher.py — HTTP page fetcher using only urllib.request (stdlib).

Fetches a web page via HTTP GET.
Returns (html_content, status_code) tuple.
Handles timeouts and HTTP errors gracefully.
"""

import urllib.request
import urllib.error


def fetch_page(url: str, timeout: int = 10) -> tuple[str, int]:
    """
    Fetch a web page using urllib.request.urlopen.

    Args:
        url: The URL to fetch.
        timeout: Request timeout in seconds (default 10).

    Returns:
        A tuple of (html_string, http_status_code).
        On error, returns (error_message, error_code).

    Raises:
        No exceptions — errors are returned as (message, code) tuples.
    """
    try:
        req = urllib.request.Request(
            url,
            headers={
                'User-Agent': 'GoogleInOneDay-Crawler/1.0 (Student Project)',
                'Accept': 'text/html,application/xhtml+xml',
            }
        )
        with urllib.request.urlopen(req, timeout=timeout) as response:
            status = response.status
            # Only process HTML content
            content_type = response.headers.get('Content-Type', '')
            if 'text/html' not in content_type and 'text/plain' not in content_type:
                return ('', status)
            # Read and decode the response body
            raw = response.read()
            encoding = response.headers.get_content_charset() or 'utf-8'
            try:
                html = raw.decode(encoding)
            except (UnicodeDecodeError, LookupError):
                html = raw.decode('utf-8', errors='replace')
            return (html, status)
    except urllib.error.HTTPError as e:
        return (str(e), e.code)
    except urllib.error.URLError as e:
        return (str(e.reason), 0)
    except Exception as e:
        return (str(e), 0)
