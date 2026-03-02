"""High-level operations API — the primary interface for CLI and AI agent skills."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import text as sa_text
from sqlalchemy.orm import Session, joinedload, selectinload

from feedcli.db import get_session
from feedcli.discovery import discover_feeds as _discover_feeds
from feedcli.fetcher import fetch_feed
from feedcli.models import Feed, Item


class FeedAlreadyExistsError(ValueError):
    """Raised when attempting to subscribe to a feed that is already in the DB."""

    def __init__(self, url: str, feed_id: int) -> None:
        self.feed_url = url
        self.feed_id = feed_id
        super().__init__(f"Feed already exists: {url} (id={feed_id})")


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
            raise FeedAlreadyExistsError(existing.url, existing.id)

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


def reset_feed_errors(
    feed_id: int, session: Session | None = None
) -> int:
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
    sess, should_close = _get_session(session)
    try:
        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")
        feed.error_count = 0
        feed.disabled = False
        feed.last_error = None
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()
    return update_feed(feed_id, session=session)


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
    starred_only: bool = False,
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
        if starred_only:
            query = query.filter(Item.is_starred == True)  # noqa: E712
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


def mark_unread(item_id: int, session: Session | None = None) -> None:
    """Mark a single item as unread."""
    sess, should_close = _get_session(session)
    try:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        item.is_read = False
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def delete_item(item_id: int, hard: bool = False, session: Session | None = None) -> None:
    """Delete an item. Soft-delete by default (sets deleted=True), hard-delete removes from DB."""
    sess, should_close = _get_session(session)
    try:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        if hard:
            sess.delete(item)
        else:
            item.deleted = True
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def search_items(
    query: str,
    feed_id: int | None = None,
    limit: int = 20,
    session: Session | None = None,
) -> list[Item]:
    """Full-text search across item titles and content."""
    sess, should_close = _get_session(session)
    try:
        # Escape SQL LIKE wildcards in user input so they're treated literally
        escaped = query.replace("!", "!!").replace("%", "!%").replace("_", "!_")
        pattern = f"%{escaped}%"
        q = (
            sess.query(Item)
            .options(joinedload(Item.feed))
            .filter(
                Item.deleted == False,  # noqa: E712
                (Item.title.ilike(pattern, escape="!"))
                | (Item.content.ilike(pattern, escape="!"))
                | (Item.summary.ilike(pattern, escape="!")),
            )
        )
        if feed_id is not None:
            q = q.filter(Item.feed_id == feed_id)
        return q.order_by(Item.published_at.desc().nullslast()).limit(limit).all()
    finally:
        if should_close:
            sess.close()


def star_item(item_id: int, session: Session | None = None) -> None:
    """Star/bookmark an item."""
    sess, should_close = _get_session(session)
    try:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        item.is_starred = True
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def unstar_item(item_id: int, session: Session | None = None) -> None:
    """Remove star from an item."""
    sess, should_close = _get_session(session)
    try:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        item.is_starred = False
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def get_starred_items(
    limit: int = 50,
    session: Session | None = None,
) -> list[Item]:
    """Get all starred items."""
    sess, should_close = _get_session(session)
    try:
        return (
            sess.query(Item)
            .options(joinedload(Item.feed))
            .filter(
                Item.is_starred == True,  # noqa: E712
                Item.deleted == False,  # noqa: E712
            )
            .order_by(Item.published_at.desc().nullslast())
            .limit(limit)
            .all()
        )
    finally:
        if should_close:
            sess.close()


def get_item_url(item_id: int, session: Session | None = None) -> str:
    """Get just the URL for an item. Useful for opening in browser."""
    item = get_item(item_id, session=session)
    return item.url


# --- Tag operations ---


def list_tags(session: Session | None = None) -> list[str]:
    """List all tags in use."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Tag

        rows = sess.query(Tag.name).distinct().order_by(Tag.name).all()
        return [row[0] for row in rows]
    finally:
        if should_close:
            sess.close()


def add_tag(
    feed_id: int, tag: str, session: Session | None = None
) -> None:
    """Add a tag to a feed."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Tag

        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")
        existing = (
            sess.query(Tag)
            .filter(Tag.feed_id == feed_id, Tag.name == tag)
            .first()
        )
        if existing:
            return  # Already tagged
        sess.add(Tag(feed_id=feed_id, name=tag))
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def remove_tag(
    feed_id: int, tag: str, session: Session | None = None
) -> None:
    """Remove a tag from a feed."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Tag

        t = (
            sess.query(Tag)
            .filter(Tag.feed_id == feed_id, Tag.name == tag)
            .first()
        )
        if not t:
            raise ValueError(
                f"Tag '{tag}' not found on feed {feed_id}"
            )
        sess.delete(t)
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def get_feeds_by_tag(
    tag: str, session: Session | None = None
) -> list[Feed]:
    """Get all feeds with a given tag."""
    return list_feeds(tag=tag, session=session)


# --- Feed discovery (public wrapper) ---


def discover_feeds(url: str, timeout: int = 30) -> list[dict]:
    """Discover feed URLs from a website URL without subscribing.

    Returns list of {url, type, version, title, items_count}.
    """
    return _discover_feeds(url, timeout=timeout)


# --- OPML operations ---


def import_opml(
    file_path: str, session: Session | None = None
) -> list[Feed]:
    """Import feeds from an OPML file. Returns list of added feeds."""
    from feedcli.opml import parse_opml

    outlines = parse_opml(file_path)
    feeds = []
    for outline in outlines:
        url = outline.get("xml_url") or outline.get("html_url")
        if not url:
            continue
        title = outline.get("title") or outline.get("text")
        tags = [outline["category"]] if outline.get("category") else None
        try:
            feed = add_feed(
                url=url,
                title=title,
                tags=tags,
                auto_discover=False,
                session=session,
            )
            feeds.append(feed)
        except FeedAlreadyExistsError:
            continue  # Duplicate — skip silently
        except ValueError as e:
            import logging

            logging.getLogger(__name__).warning(
                "Skipping %s: %s", url, e
            )
            continue
    return feeds


def export_opml(
    file_path: str, session: Session | None = None
) -> None:
    """Export all feeds to an OPML file."""
    from feedcli.opml import generate_opml

    feeds = list_feeds(session=session)
    generate_opml(feeds, file_path)


# --- Config operations ---


def get_config() -> dict:
    """Get current configuration as a dictionary."""
    from feedcli.config import load_config

    return load_config()


def set_config(key: str, value: str) -> None:
    """Set a configuration value."""
    from feedcli.config import save_config

    save_config(key, value)


# --- Database operations ---


def db_info(session: Session | None = None) -> dict:
    """Get database stats: feed count, item count, DB file size, etc."""
    from feedcli.config import load_config

    sess, should_close = _get_session(session)
    try:
        feed_count = sess.query(Feed).count()
        item_count = sess.query(Item).count()
        unread_count = (
            sess.query(Item)
            .filter(
                Item.is_read == False,  # noqa: E712
                Item.deleted == False,  # noqa: E712
            )
            .count()
        )
        starred_count = (
            sess.query(Item)
            .filter(
                Item.is_starred == True,  # noqa: E712
                Item.deleted == False,  # noqa: E712
            )
            .count()
        )

        config = load_config()
        db_path = config["db_path"]

        import os

        db_size = None
        if db_path != ":memory:" and os.path.exists(db_path):
            db_size = os.path.getsize(db_path)

        return {
            "db_path": db_path,
            "db_size_bytes": db_size,
            "feed_count": feed_count,
            "item_count": item_count,
            "unread_count": unread_count,
            "starred_count": starred_count,
        }
    finally:
        if should_close:
            sess.close()


def db_vacuum() -> None:
    """Compact the SQLite database."""
    from feedcli.db import get_engine

    engine = get_engine()
    with engine.connect() as conn:
        conn.execute(sa_text("VACUUM"))
        conn.commit()


def db_backup(dest_path: str) -> None:
    """Backup the database to a file."""
    import shutil

    from feedcli.config import load_config

    config = load_config()
    src = config["db_path"]
    if src == ":memory:":
        raise ValueError("Cannot backup an in-memory database")
    shutil.copy2(src, dest_path)


def db_restore(src_path: str) -> None:
    """Restore the database from a backup file."""
    import os
    import shutil

    from feedcli.config import load_config
    from feedcli.db import reset_engine

    if not os.path.exists(src_path):
        raise ValueError(f"Backup file not found: {src_path}")

    config = load_config()
    dest = config["db_path"]
    if dest == ":memory:":
        raise ValueError("Cannot restore to an in-memory database")
    shutil.copy2(src_path, dest)
    reset_engine()
