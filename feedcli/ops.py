"""High-level operations API — the primary interface for CLI and AI agent skills."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session, joinedload, selectinload

from feedcli.db import get_session
from feedcli.discovery import discover_feeds as _discover_feeds
from feedcli.fetcher import fetch_feed
from feedcli.models import Feed, Item


def _get_session(session: Session | None) -> tuple[Session, bool]:
    """Return the given session or create a new one. Returns (session, should_close)."""
    if session is not None:
        return session, False
    return get_session(), True


def add_feed(
    url: str,
    title: str | None = None,
    tags: list[str] | None = None,
    auto_discover: bool = True,
    session: Session | None = None,
) -> Feed:
    """Subscribe to a feed. Auto-discovers feed URL from website URL by default."""
    sess, should_close = _get_session(session)
    try:
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
            raise ValueError(f"Feed already exists: {existing.url} (id={existing.id})")

        feed = Feed(
            url=feed_url,
            title=title or discovered_title or feed_url,
            website=url if url != feed_url else None,
            created_at=datetime.now(timezone.utc),
        )
        sess.add(feed)
        sess.flush()

        if tags:
            from feedcli.models import Tag

            for tag_name in tags:
                sess.add(Tag(feed_id=feed.id, name=tag_name))

        sess.commit()
        return feed
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def list_feeds(
    tag: str | None = None,
    session: Session | None = None,
) -> list[Feed]:
    """List all subscribed feeds. Optionally filter by tag."""
    sess, should_close = _get_session(session)
    try:
        query = sess.query(Feed).options(selectinload(Feed.tags))
        if tag:
            from feedcli.models import Tag

            query = query.join(Feed.tags).filter(Tag.name == tag)
        return query.order_by(Feed.id).all()
    finally:
        if should_close:
            sess.close()


def get_feed(feed_id: int, session: Session | None = None) -> Feed:
    """Get a single feed by ID."""
    sess, should_close = _get_session(session)
    try:
        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")
        return feed
    finally:
        if should_close:
            sess.close()


def delete_feed(feed_id: int, session: Session | None = None) -> None:
    """Delete a feed and all its items."""
    sess, should_close = _get_session(session)
    try:
        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")
        sess.delete(feed)
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def update_feed(
    feed_id: int,
    timeout: int = 30,
    session: Session | None = None,
) -> int:
    """Fetch new items for a single feed. Returns count of new items."""
    sess, should_close = _get_session(session)
    try:
        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")
        return fetch_feed(feed, sess, timeout=timeout)
    finally:
        if should_close:
            sess.close()


def update_all_feeds(
    jobs: int = 4,
    timeout: int = 30,
    session: Session | None = None,
) -> dict[int, int]:
    """Fetch new items for all feeds (single-threaded for MVP).

    Returns {feed_id: new_item_count}.
    """
    sess, should_close = _get_session(session)
    try:
        feeds = sess.query(Feed).filter(Feed.disabled == False).all()  # noqa: E712
        results = {}
        for feed in feeds:
            count = fetch_feed(feed, sess, timeout=timeout)
            results[feed.id] = count
        return results
    finally:
        if should_close:
            sess.close()


def get_unread_items(
    feed_id: int | None = None,
    limit: int = 50,
    session: Session | None = None,
) -> list[Item]:
    """Get unread items, optionally filtered by feed. Ordered by published_at desc."""
    sess, should_close = _get_session(session)
    try:
        query = (
            sess.query(Item)
            .options(joinedload(Item.feed))
            .filter(Item.is_read == False, Item.deleted == False)  # noqa: E712
        )
        if feed_id is not None:
            query = query.filter(Item.feed_id == feed_id)
        return query.order_by(Item.published_at.desc().nullslast()).limit(limit).all()
    finally:
        if should_close:
            sess.close()


def get_items(
    feed_id: int | None = None,
    unread_only: bool = False,
    limit: int = 50,
    offset: int = 0,
    session: Session | None = None,
) -> list[Item]:
    """Get items with flexible filtering."""
    sess, should_close = _get_session(session)
    try:
        query = (
            sess.query(Item).options(joinedload(Item.feed)).filter(Item.deleted == False)  # noqa: E712
        )
        if feed_id is not None:
            query = query.filter(Item.feed_id == feed_id)
        if unread_only:
            query = query.filter(Item.is_read == False)  # noqa: E712
        return (
            query.order_by(Item.published_at.desc().nullslast())
            .offset(offset)
            .limit(limit)
            .all()
        )
    finally:
        if should_close:
            sess.close()


def get_item(item_id: int, session: Session | None = None) -> Item:
    """Get a single item by ID."""
    sess, should_close = _get_session(session)
    try:
        item = sess.query(Item).options(joinedload(Item.feed)).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        return item
    finally:
        if should_close:
            sess.close()


def mark_read(item_id: int, session: Session | None = None) -> None:
    """Mark a single item as read."""
    sess, should_close = _get_session(session)
    try:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        item.is_read = True
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def mark_all_read(
    feed_id: int | None = None,
    session: Session | None = None,
) -> int:
    """Mark all items (or all items in a feed) as read. Returns count affected."""
    sess, should_close = _get_session(session)
    try:
        query = sess.query(Item).filter(Item.is_read == False)  # noqa: E712
        if feed_id is not None:
            query = query.filter(Item.feed_id == feed_id)
        count = query.update({Item.is_read: True})
        sess.commit()
        return count
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()
