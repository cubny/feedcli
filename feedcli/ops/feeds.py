"""Feed CRUD, update, and discovery operations."""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload

from feedcli.discovery import discover_feeds as _discover_feeds
from feedcli.fetcher import fetch_feed
from feedcli.models import Category, Feed

from ._session import managed_session

log = logging.getLogger(__name__)


class FeedAlreadyExistsError(ValueError):
    """Raised when attempting to subscribe to a feed that is already in the DB."""

    def __init__(self, url: str, feed_id: int) -> None:
        self.feed_url = url
        self.feed_id = feed_id
        super().__init__(f"Feed already exists: {url} (id={feed_id})")


def add_feed(
    url: str,
    title: str | None = None,
    category: str | None = None,
    auto_discover: bool = True,
    session: Session | None = None,
) -> Feed:
    """Subscribe to a feed. Auto-discovers feed URL from website URL by default."""
    with managed_session(session, commit=True) as sess:
        feed_url = url
        discovered_title = None

        if auto_discover:
            candidates = _discover_feeds(url)
            if candidates:
                feed_url = candidates[0]["url"]
                discovered_title = candidates[0].get("title")

        # Check for existing feed
        existing = sess.query(Feed).filter(Feed.url == feed_url).first()
        if existing:
            raise FeedAlreadyExistsError(existing.url, existing.id)

        cat_name = category or "default"
        cat = sess.query(Category).filter(Category.name == cat_name).first()
        if not cat:
            cat = Category(name=cat_name)
            sess.add(cat)
            sess.flush()

        feed = Feed(
            url=feed_url,
            title=title or discovered_title or feed_url,
            website=url if url != feed_url else None,
            category_id=cat.id,
            created_at=datetime.now(timezone.utc),
        )
        sess.add(feed)

        return feed


def list_feeds(
    category: str | None = None,
    session: Session | None = None,
) -> list[Feed]:
    """List all subscribed feeds. Optionally filter by category."""
    with managed_session(session) as sess:
        query = sess.query(Feed).options(joinedload(Feed.category))
        if category:
            query = query.join(Feed.category).filter(Category.name == category)
        return query.order_by(Feed.id).all()


def get_feed(feed_id: int, session: Session | None = None) -> Feed:
    """Get a single feed by ID."""
    with managed_session(session) as sess:
        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")
        return feed


def delete_feed(feed_id: int, session: Session | None = None) -> None:
    """Delete a feed and all its items."""
    with managed_session(session, commit=True) as sess:
        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")
        sess.delete(feed)


def update_feed(
    feed_id: int,
    timeout: int = 30,
    session: Session | None = None,
) -> int:
    """Fetch new items for a single feed. Returns count of new items."""
    with managed_session(session) as sess:
        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")
        return fetch_feed(feed, sess, timeout=timeout)


def update_all_feeds(
    jobs: int = 4,
    timeout: int = 30,
    session: Session | None = None,
) -> dict[int, int]:
    """Fetch new items for all feeds (single-threaded for MVP).

    Returns {feed_id: new_item_count}.
    """
    with managed_session(session) as sess:
        feeds = sess.query(Feed).filter(Feed.disabled == False).all()  # noqa: E712
        results = {}
        for feed in feeds:
            count = fetch_feed(feed, sess, timeout=timeout)
            results[feed.id] = count
        return results


def reset_feed_errors(feed_id: int, session: Session | None = None) -> int:
    """Reset error state for a feed and immediately fetch it.

    Clears error_count, disabled, and last_error, then calls update_feed.
    Returns count of new items fetched.

    Implementation note — intentional two-phase commit:
    - Phase 1: reset error fields and commit (or rollback on error).
      When session=None an internal session is opened, committed, then closed.
    - Phase 2: update_feed() is called with the original session argument.
      When session=None a fresh session is opened for the fetch, which is
      correct. When an explicit session is passed, both phases share it and
      each phase issues its own commit.
    """
    with managed_session(session, commit=True) as sess:
        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")
        feed.error_count = 0
        feed.disabled = False
        feed.last_error = None
    return update_feed(feed_id, session=session)


def discover_feeds(url: str, timeout: int = 30) -> list[dict]:
    """Discover feed URLs from a website URL without subscribing.

    Returns list of {url, type, version, title, items_count}.
    """
    return _discover_feeds(url, timeout=timeout)
