"""
router.py — URL routing for the HTTP API.

Maps HTTP method + path patterns to handler functions.
Supports path parameters like /crawl/{id} via regex matching.
"""

import re


class Route:
    """A single route definition: method + URL pattern → handler."""

    def __init__(self, method: str, pattern: str, handler):
        """
        Args:
            method: HTTP method (GET, POST, etc.)
            pattern: URL pattern string. Use {name} for path parameters.
            handler: Callable(request_handler, **path_params)
        """
        self.method = method.upper()
        self.handler = handler
        # Convert pattern like /crawl/{id} to regex /crawl/(?P<id>[^/]+)
        regex_pattern = re.sub(r'\{(\w+)\}', r'(?P<\1>[^/]+)', pattern)
        self._regex = re.compile(f'^{regex_pattern}$')

    def match(self, method: str, path: str) -> dict | None:
        """
        Try to match a request against this route.

        Returns:
            Dict of path parameters if matched, None otherwise.
        """
        if method.upper() != self.method:
            return None
        # Strip query string before matching
        clean_path = path.split('?')[0]
        m = self._regex.match(clean_path)
        if m:
            return m.groupdict()
        return None


class Router:
    """Simple HTTP router that dispatches requests to handler functions."""

    def __init__(self):
        self._routes: list[Route] = []

    def add_route(self, method: str, pattern: str, handler) -> None:
        """Register a route."""
        self._routes.append(Route(method, pattern, handler))

    def get(self, pattern: str, handler) -> None:
        """Shortcut for add_route('GET', ...)."""
        self.add_route('GET', pattern, handler)

    def post(self, pattern: str, handler) -> None:
        """Shortcut for add_route('POST', ...)."""
        self.add_route('POST', pattern, handler)

    def resolve(self, method: str, path: str):
        """
        Find a matching route for the given method and path.

        Returns:
            (handler, path_params) tuple if found, (None, {}) otherwise.
        """
        for route in self._routes:
            params = route.match(method, path)
            if params is not None:
                return (route.handler, params)
        return (None, {})
