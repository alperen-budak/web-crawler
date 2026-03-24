"""
search.py — Query engine for the word index.

Tokenizes a query into words, reads the SQLite database,
aggregates results by URL, and returns them sorted by relevance score.

Relevance score formula:
    score = (frequency × 10) + 1000 (exact match bonus) − (depth × 5)
"""

from src.searcher.index_reader import IndexReader


def _calculate_relevance_score(frequency: int, depth: int) -> int:
    """
    Calculate relevance score for a search result.

    Formula: score = (frequency × 10) + 1000 (exact match bonus) − (depth × 5)
    """
    return (frequency * 10) + 1000 - (depth * 5)


def search(
    query: str,
    page: int = 1,
    size: int = 10,
    sort_by: str = 'relevance',
    data_dir: str | None = None,
) -> dict:
    """
    Search the word index for a query string.

    Args:
        query: Space-separated search terms.
        page: Page number (1-based).
        size: Results per page.
        sort_by: Sort order — 'relevance' (default) or 'frequency'.
        data_dir: Optional override for the storage directory.

    Returns:
        Dict with keys:
            results: list of {url, origin_url, depth, frequency, relevance_score}
            total: total number of matching results
            page: current page number
    """
    reader = IndexReader(data_dir=data_dir)
    words = [w.lower().strip() for w in query.split() if w.strip()]

    if not words:
        return {'results': [], 'total': 0, 'page': page}

    # Collect all matching entries across all query words
    all_entries: list[dict] = []
    for word in words:
        entries = reader.read_word(word)
        all_entries.extend(entries)

    # Aggregate by URL: sum frequencies for the same URL
    url_map: dict[str, dict] = {}
    for entry in all_entries:
        url = entry.get('url', '')
        key = url
        if key not in url_map:
            url_map[key] = {
                'url': url,
                'origin_url': entry.get('origin', ''),
                'depth': entry.get('depth', 0),
                'frequency': entry.get('freq', 0),
            }
        else:
            # Sum frequencies for same URL
            url_map[key]['frequency'] += entry.get('freq', 0)

    # Calculate relevance score for each result
    for result in url_map.values():
        result['relevance_score'] = _calculate_relevance_score(
            result['frequency'], result['depth']
        )

    # Sort by chosen criterion
    if sort_by == 'frequency':
        results = sorted(url_map.values(), key=lambda x: x['frequency'], reverse=True)
    else:
        # Default: sort by relevance_score descending
        results = sorted(url_map.values(), key=lambda x: x['relevance_score'], reverse=True)

    total = len(results)

    # Paginate
    start = (page - 1) * size
    end = start + size
    page_results = results[start:end]

    return {
        'results': page_results,
        'total': total,
        'page': page,
    }
