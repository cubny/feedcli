"""Feed fetching, parsing, and item storage."""

from __future__ import annotations

from datetime import datetime, timezone

import feedparser
import httpx
from sqlalchemy.orm import Session

from feedcli.models import Feed, Item
from feedcli.utils import parse_date


def fetch_feed(feed: Feed, session: Session, timeout: int = 30) -> int:
    """Fetch new items for a feed. Returns count of new items added.

    Uses conditional GET (ETag/Last-Modified) when available.
    Records errors in feed.last_error/error_count.
    """
    headers: dict[str, str] = {}
    if feed.etag:
        headers["If-None-Match"] = feed.etag
    if feed.last_modified:
        headers["If-Modified-Since"] = feed.last_modified

    try:
        resp = httpx.get(feed.url, headers=headers, timeout=timeout, follow_redirects=True)
    except (httpx.HTTPError, httpx.InvalidURL) as e:
        feed.last_error = str(e)
        feed.error_count = (feed.error_count or 0) + 1
        feed.last_fetched_at = datetime.now(timezone.utc)
        session.commit()
        return 0

    feed.last_fetched_at = datetime.now(timezone.utc)

    if resp.status_code == 304:
        # Not modified
        feed.last_error = None
        feed.error_count = 0
        session.commit()
        return 0

    if resp.status_code >= 400:
        feed.last_error = f"HTTP {resp.status_code}"
        feed.error_count = (feed.error_count or 0) + 1
        session.commit()
        return 0

    # Update conditional GET headers
    if "etag" in resp.headers:
        feed.etag = resp.headers["etag"]
    if "last-modified" in resp.headers:
        feed.last_modified = resp.headers["last-modified"]

    parsed = feedparser.parse(resp.text)
    if not parsed.version:
        feed.last_error = "Failed to parse feed"
        feed.error_count = (feed.error_count or 0) + 1
        session.commit()
        return 0

    # Update feed title from parsed feed if not set
    if not feed.title and parsed.feed.get("title"):
        feed.title = parsed.feed["title"]

    # Update website from feed link
    if not feed.website and parsed.feed.get("link"):
        feed.website = parsed.feed["link"]

    new_count = 0
    now = datetime.now(timezone.utc)

    for entry in parsed.entries:
        guid = entry.get("id") or entry.get("link")
        entry_url = entry.get("link", "")

        if not guid and not entry_url:
            continue

        # Dedup by (feed_id, guid) or fallback (feed_id, url)
        existing = None
        if guid:
            existing = (
                session.query(Item)
                .filter(Item.feed_id == feed.id, Item.guid == guid)
                .first()
            )
        if not existing and entry_url:
            existing = (
                session.query(Item)
                .filter(Item.feed_id == feed.id, Item.url == entry_url, Item.guid.is_(None))
                .first()
            )

        if existing:
            continue

        # Extract summary and content
        summary = ""
        if entry.get("summary"):
            summary = entry["summary"]

        content = ""
        if entry.get("content"):
            # feedparser content is a list of dicts with 'value' key
            content = entry["content"][0].get("value", "") if entry["content"] else ""

        published = parse_date(entry.get("published") or entry.get("updated"))

        item = Item(
            feed_id=feed.id,
            guid=guid,
            title=entry.get("title", ""),
            url=entry_url,
            author=entry.get("author", ""),
            summary=summary,
            content=content,
            published_at=published,
            fetched_at=now,
            is_read=False,
            is_starred=False,
            deleted=False,
        )
        session.add(item)
        new_count += 1

    feed.last_error = None
    feed.error_count = 0
    session.commit()
    return new_count
