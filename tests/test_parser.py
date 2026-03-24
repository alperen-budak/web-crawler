"""Tests for src/crawler/parser.py — HTML link and word extraction."""

import unittest

from src.crawler.parser import parse_page


class TestParser(unittest.TestCase):
    """Unit tests for the parse_page function."""

    def test_parse_extracts_absolute_links(self):
        """Absolute <a href> URLs should appear in the returned links list."""
        html = '<html><body><a href="https://test.com/page">Link</a></body></html>'
        links, words = parse_page(html, base_url='https://example.com')

        self.assertIn('https://test.com/page', links)

    def test_parse_converts_relative_links_to_absolute(self):
        """Relative hrefs should be resolved against the base_url."""
        html = '<html><body><a href="/about">About</a></body></html>'
        links, words = parse_page(html, base_url='https://example.com')

        self.assertIn('https://example.com/about', links)

    def test_parse_ignores_mailto_and_javascript_links(self):
        """mailto: and javascript: hrefs should be filtered out."""
        html = (
            '<html><body>'
            '<a href="mailto:user@example.com">Email</a>'
            '<a href="javascript:void(0)">JS</a>'
            '<a href="https://valid.com">Valid</a>'
            '</body></html>'
        )
        links, words = parse_page(html, base_url='https://example.com')

        self.assertNotIn('mailto:user@example.com', links)
        self.assertNotIn('javascript:void(0)', links)
        self.assertIn('https://valid.com', links)

    def test_parse_extracts_words_from_text(self):
        """Visible text content should be extracted as lowercase words."""
        html = '<html><body><p>hello world python</p></body></html>'
        links, words = parse_page(html, base_url='https://example.com')

        self.assertIn('hello', words)
        self.assertIn('world', words)
        self.assertIn('python', words)

    def test_parse_counts_word_frequency(self):
        """Duplicate words should appear multiple times in the words list."""
        html = '<html><body><p>python python crawler</p></body></html>'
        links, words = parse_page(html, base_url='https://example.com')

        self.assertEqual(words.count('python'), 2)
        self.assertEqual(words.count('crawler'), 1)

    def test_parse_ignores_empty_html(self):
        """Empty HTML string should return empty lists without crashing."""
        links, words = parse_page('', base_url='https://example.com')

        self.assertEqual(links, [])
        self.assertEqual(words, [])

    def test_parse_strips_html_tags_from_words(self):
        """HTML tag names should not appear as extracted words."""
        html = '<html><body><div><span>actual content</span></div></body></html>'
        links, words = parse_page(html, base_url='https://example.com')

        # Tag names should not be in the word list
        for tag in ['html', 'body', 'div', 'span']:
            self.assertNotIn(tag, words)
        # Actual text should be present
        self.assertIn('actual', words)
        self.assertIn('content', words)

    def test_parse_ignores_script_and_style_content(self):
        """Text inside <script> and <style> tags should not be indexed."""
        html = (
            '<html><body>'
            '<script>var x = "hidden";</script>'
            '<style>.cls { color: red; }</style>'
            '<p>visible text</p>'
            '</body></html>'
        )
        links, words = parse_page(html, base_url='https://example.com')

        self.assertNotIn('hidden', words)
        self.assertNotIn('color', words)
        self.assertIn('visible', words)
        self.assertIn('text', words)

    def test_parse_handles_multiple_links(self):
        """Multiple <a> tags should all be collected."""
        html = (
            '<html><body>'
            '<a href="https://a.com">A</a>'
            '<a href="https://b.com">B</a>'
            '<a href="https://c.com">C</a>'
            '</body></html>'
        )
        links, words = parse_page(html, base_url='https://example.com')

        self.assertEqual(len(links), 3)
        self.assertIn('https://a.com', links)
        self.assertIn('https://b.com', links)
        self.assertIn('https://c.com', links)

    def test_parse_removes_fragment_from_links(self):
        """URL fragments (#section) should be stripped from extracted links."""
        html = '<html><body><a href="https://test.com/page#section">Link</a></body></html>'
        links, words = parse_page(html, base_url='https://example.com')

        self.assertIn('https://test.com/page', links)
        # The fragment version should not appear separately
        self.assertNotIn('https://test.com/page#section', links)

    def test_parse_words_are_lowercase(self):
        """All extracted words should be lowercased."""
        html = '<html><body><p>Hello WORLD Python</p></body></html>'
        links, words = parse_page(html, base_url='https://example.com')

        for word in words:
            self.assertEqual(word, word.lower(),
                             f"Word '{word}' should be lowercase")

    def test_parse_ignores_short_words(self):
        """Single-character words should be filtered out (min length 2)."""
        html = '<html><body><p>I a am ok to go do it</p></body></html>'
        links, words = parse_page(html, base_url='https://example.com')

        # Single-char tokens should be excluded
        self.assertNotIn('i', words)
        self.assertNotIn('a', words)


if __name__ == '__main__':
    unittest.main()
