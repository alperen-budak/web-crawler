"""
parser.py — HTML parser using html.parser.HTMLParser (stdlib).

Extracts:
  - <a href> links (resolved to absolute URLs)
  - Text words from the page body

No third-party libraries (BeautifulSoup, lxml, etc.) are used.
"""

import re
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse


class _PageParser(HTMLParser):
    """HTMLParser subclass that collects links and text words."""

    # Tags whose content should be ignored (not indexed as words)
    # NOTE: void elements (meta, link, br, img …) must NOT be listed here
    # because HTMLParser never fires handle_endtag for them, which would
    # leave _skip_depth permanently elevated and suppress all later text.
    SKIP_TAGS = {'script', 'style', 'noscript', 'head'}

    def __init__(self, base_url: str):
        super().__init__()
        self.base_url = base_url
        self.links: list[str] = []
        self.words: list[str] = []
        self._skip_depth = 0  # > 0 means we are inside a SKIP_TAG

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag_lower = tag.lower()

        # Track skip tags
        if tag_lower in self.SKIP_TAGS:
            self._skip_depth += 1

        # Extract links from <a href="...">
        if tag_lower == 'a':
            for attr, val in attrs:
                if attr.lower() == 'href' and val:
                    resolved = self._resolve_url(val)
                    if resolved:
                        self.links.append(resolved)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() in self.SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._skip_depth > 0:
            return
        # Extract words: sequences of alphanumeric characters (min length 2)
        tokens = re.findall(r'[a-zA-Z0-9\u00C0-\u024F]+', data)
        for token in tokens:
            word = token.lower().strip()
            if len(word) >= 2:
                self.words.append(word)

    def _resolve_url(self, href: str) -> str | None:
        """Resolve a relative URL to an absolute one, filtering non-HTTP schemes."""
        href = href.strip()
        # Skip fragments, javascript:, mailto:, tel:, data: etc.
        if href.startswith('#') or href.startswith('javascript:') or \
           href.startswith('mailto:') or href.startswith('tel:') or \
           href.startswith('data:'):
            return None
        resolved = urljoin(self.base_url, href)
        parsed = urlparse(resolved)
        if parsed.scheme not in ('http', 'https'):
            return None
        # Remove fragment
        clean = parsed._replace(fragment='').geturl()
        return clean


def parse_page(html: str, base_url: str) -> tuple[list[str], list[str]]:
    """
    Parse an HTML page and extract links and words.

    Args:
        html: Raw HTML string.
        base_url: The URL of the page (used to resolve relative links).

    Returns:
        A tuple of (links, words) where:
        - links: list of absolute URLs found in <a href> tags
        - words: list of lowercase words extracted from visible text
    """
    parser = _PageParser(base_url)
    try:
        parser.feed(html)
    except Exception:
        pass  # Tolerate malformed HTML
    return (parser.links, parser.words)
