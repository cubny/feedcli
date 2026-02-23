"""Feed URL discovery from website URLs."""

from __future__ import annotations

from urllib.parse import urljoin

import feedparser
import httpx
from bs4 import BeautifulSoup

FEED_CONTENT_TYPES = {
    "application/rss+xml",
    "application/atom+xml",
    "application/feed+json",
    "application/xml",
    "text/xml",
}

WELL_KNOWN_PATHS = [
    "/feed.json",
    "/.well-known/feed+json",
]

COMMON_ENDPOINTS = [
    "/feed",
    "/rss",
    "/rss.xml",
    "/atom.xml",
    "/?feed=rss2",
    "/feeds/posts/default",
]


def _is_feed_content_type(content_type: str) -> bool:
    ct = content_type.split(";")[0].strip().lower()
    return ct in FEED_CONTENT_TYPES or ct in ("text/xml", "application/xml")


def _probe_feed(url: str, timeout: int = 30) -> dict | None:
    """Probe a URL to see if it's a valid feed. Returns feed info dict or None."""
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.InvalidURL):
        return None

    parsed = feedparser.parse(resp.text)
    if parsed.version:
        return {
            "url": url,
            "type": parsed.version,
            "title": parsed.feed.get("title", ""),
            "items_count": len(parsed.entries),
        }
    return None


def discover_feeds(url: str, timeout: int = 30) -> list[dict]:
    """Discover feed URLs from a website URL.

    Algorithm:
    1. Direct probe — check if URL itself is a feed
    2. HTML link tags — parse <link rel="alternate"> tags
    3. Well-known paths — try /feed.json, /.well-known/feed+json
    4. Common endpoints — try /feed, /rss, /rss.xml, etc.
    5. Validate and deduplicate
    """
    candidates: list[dict] = []
    seen_urls: set[str] = set()

    def _add_candidate(info: dict):
        if info["url"] not in seen_urls:
            seen_urls.add(info["url"])
            candidates.append(info)

    # Step 1: Direct probe
    info = _probe_feed(url, timeout)
    if info:
        _add_candidate(info)
        return candidates  # It's already a feed, no need to discover

    # Step 2: HTML link tags
    try:
        resp = httpx.get(url, timeout=timeout, follow_redirects=True)
        resp.raise_for_status()
    except (httpx.HTTPError, httpx.InvalidURL):
        return candidates

    soup = BeautifulSoup(resp.text, "html.parser")
    link_types = [
        "application/rss+xml",
        "application/atom+xml",
        "application/feed+json",
        "application/xml",
        "text/xml",
    ]
    for link_type in link_types:
        for link in soup.find_all("link", type=link_type):
            href = link.get("href")
            if href:
                feed_url = urljoin(url, href)
                info = _probe_feed(feed_url, timeout)
                if info:
                    _add_candidate(info)

    if candidates:
        return candidates

    # Step 3: Well-known paths
    for path in WELL_KNOWN_PATHS:
        feed_url = urljoin(url, path)
        info = _probe_feed(feed_url, timeout)
        if info:
            _add_candidate(info)

    if candidates:
        return candidates

    # Step 4: Common endpoints
    for path in COMMON_ENDPOINTS:
        feed_url = urljoin(url, path)
        info = _probe_feed(feed_url, timeout)
        if info:
            _add_candidate(info)

    return candidates
