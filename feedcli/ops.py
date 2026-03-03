"""High-level operations API — the primary interface for CLI and AI agent skills."""

from __future__ import annotations

import warnings
from datetime import datetime, timezone

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
    category: str | None = None,
    auto_discover: bool = True,
    session: Session | None = None,
) -> Feed:
    """Subscribe to a feed. Auto-discovers feed URL from website URL by default."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Category

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

        sess.commit()
        return feed
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def list_feeds(
    category: str | None = None,
    session: Session | None = None,
) -> list[Feed]:
    """List all subscribed feeds. Optionally filter by category."""
    sess, should_close = _get_session(session)
    try:
        query = sess.query(Feed).options(joinedload(Feed.category))
        if category:
            from feedcli.models import Category

            query = query.join(Feed.category).filter(Category.name == category)
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
    tag: str | None = None,
    limit: int = 50,
    session: Session | None = None,
) -> list[Item]:
    """Get unread items, optionally filtered by feed or tag. Ordered by published_at desc."""
    sess, should_close = _get_session(session)
    try:
        query = (
            sess.query(Item)
            .options(joinedload(Item.feed), selectinload(Item.tags))
            .filter(Item.is_read == False, Item.deleted == False)  # noqa: E712
        )
        if feed_id is not None:
            query = query.filter(Item.feed_id == feed_id)
        if tag is not None:
            from feedcli.models import ItemTag

            query = query.join(Item.tags).filter(ItemTag.name == tag)
        return query.order_by(Item.published_at.desc().nullslast()).limit(limit).all()
    finally:
        if should_close:
            sess.close()


def get_items(
    feed_id: int | None = None,
    tag: str | None = None,
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
            sess.query(Item)
            .options(joinedload(Item.feed), selectinload(Item.tags))
            .filter(Item.deleted == False)  # noqa: E712
        )
        if feed_id is not None:
            query = query.filter(Item.feed_id == feed_id)
        if tag is not None:
            from feedcli.models import ItemTag

            query = query.join(Item.tags).filter(ItemTag.name == tag)
        if unread_only:
            query = query.filter(Item.is_read == False)  # noqa: E712
        if starred_only:
            query = query.filter(Item.is_starred == True)  # noqa: E712
        return (
            query.order_by(Item.published_at.desc().nullslast()).offset(offset).limit(limit).all()
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
    tag: str | None = None,
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
            .options(joinedload(Item.feed), selectinload(Item.tags))
            .filter(
                Item.deleted == False,  # noqa: E712
                (Item.title.ilike(pattern, escape="!"))
                | (Item.content.ilike(pattern, escape="!"))
                | (Item.summary.ilike(pattern, escape="!")),
            )
        )
        if feed_id is not None:
            q = q.filter(Item.feed_id == feed_id)
        if tag is not None:
            from feedcli.models import ItemTag

            q = q.join(Item.tags).filter(ItemTag.name == tag)
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


# --- Category operations ---


def list_categories(session: Session | None = None) -> list[str]:
    """List all categories in use."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Category

        rows = sess.query(Category.name).distinct().order_by(Category.name).all()
        return [row[0] for row in rows]
    finally:
        if should_close:
            sess.close()


def create_category(name: str, session: Session | None = None) -> None:
    """Create a new category."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Category

        existing = sess.query(Category).filter(Category.name == name).first()
        if existing:
            return
        sess.add(Category(name=name))
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def delete_category(name: str, move_to: str = "default", session: Session | None = None) -> None:
    """Delete a category and move its feeds to another category."""
    if name == "default":
        raise ValueError("Cannot delete the default category")
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Category, Feed

        cat = sess.query(Category).filter(Category.name == name).first()
        if not cat:
            raise ValueError(f"Category not found: {name}")

        target_cat = sess.query(Category).filter(Category.name == move_to).first()
        if not target_cat:
            target_cat = Category(name=move_to)
            sess.add(target_cat)
            sess.flush()

        sess.query(Feed).filter(Feed.category_id == cat.id).update(
            {Feed.category_id: target_cat.id}
        )
        sess.delete(cat)
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def rename_category(old_name: str, new_name: str, session: Session | None = None) -> None:
    """Rename a category."""
    if old_name == "default":
        raise ValueError("Cannot rename the default category")
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Category

        cat = sess.query(Category).filter(Category.name == old_name).first()
        if not cat:
            raise ValueError(f"Category not found: {old_name}")

        existing_new = sess.query(Category).filter(Category.name == new_name).first()
        if existing_new:
            raise ValueError(f"Category already exists: {new_name}")

        cat.name = new_name
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def set_feed_category(feed_id: int, name: str, session: Session | None = None) -> None:
    """Set the category for a feed."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Category, Feed

        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")

        cat = sess.query(Category).filter(Category.name == name).first()
        if not cat:
            cat = Category(name=name)
            sess.add(cat)
            sess.flush()

        feed.category_id = cat.id
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def reset_feed_category(feed_id: int, session: Session | None = None) -> None:
    """Reset a feed's category to 'default'."""
    set_feed_category(feed_id, "default", session=session)


def get_feeds_by_category(name: str, session: Session | None = None) -> list[Feed]:
    """Get all feeds with a given category."""
    return list_feeds(category=name, session=session)


# --- Item Tag operations ---


def tag_item(item_id: int, tag: str, session: Session | None = None) -> None:
    """Add a tag to an item."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Item, ItemTag

        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")

        existing = (
            sess.query(ItemTag).filter(ItemTag.item_id == item_id, ItemTag.name == tag).first()
        )
        if existing:
            return

        sess.add(ItemTag(item_id=item_id, name=tag))
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def untag_item(item_id: int, tag: str, session: Session | None = None) -> None:
    """Remove a tag from an item."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import ItemTag

        t = sess.query(ItemTag).filter(ItemTag.item_id == item_id, ItemTag.name == tag).first()
        if not t:
            raise ValueError(f"Tag '{tag}' not found on item {item_id}")

        sess.delete(t)
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def list_item_tags(item_id: int | None = None, session: Session | None = None) -> list[str]:
    """List distinct tags, optionally filtered by item."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import ItemTag

        query = sess.query(ItemTag.name).distinct()
        if item_id is not None:
            query = query.filter(ItemTag.item_id == item_id)

        rows = query.order_by(ItemTag.name).all()
        return [row[0] for row in rows]
    finally:
        if should_close:
            sess.close()


def get_items_by_tag(tag: str, limit: int = 50, session: Session | None = None) -> list[Item]:
    """Get items with a given tag."""
    return get_items(tag=tag, limit=limit, session=session)


def delete_tag(tag: str, delete_items: bool = False, session: Session | None = None) -> None:
    """Delete a tag from all items. Optionally delete the associated items."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import Item, ItemTag

        if delete_items:
            item_ids = [
                row[0] for row in sess.query(ItemTag.item_id).filter(ItemTag.name == tag).all()
            ]
            if item_ids:
                sess.query(Item).filter(Item.id.in_(item_ids)).update(
                    {Item.deleted: True}, synchronize_session=False
                )

        sess.query(ItemTag).filter(ItemTag.name == tag).delete(synchronize_session=False)
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


def rename_tag(old_name: str, new_name: str, session: Session | None = None) -> None:
    """Rename a tag across all items."""
    sess, should_close = _get_session(session)
    try:
        from feedcli.models import ItemTag

        # To avoid unique constraint violations, only update tags where the item doesn't
        # already have the new tag. Then delete the remaining old tags.
        items_with_new = [
            row[0] for row in sess.query(ItemTag.item_id).filter(ItemTag.name == new_name).all()
        ]

        sess.query(ItemTag).filter(
            ItemTag.name == old_name, ~ItemTag.item_id.in_(items_with_new)
        ).update({ItemTag.name: new_name}, synchronize_session=False)
        sess.query(ItemTag).filter(ItemTag.name == old_name).delete(synchronize_session=False)

        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        if should_close:
            sess.close()


# --- Deprecated Tag operations aliases ---


def list_tags(session: Session | None = None) -> list[str]:
    warnings.warn(
        "'list_tags' is deprecated, use 'list_categories' instead", DeprecationWarning, stacklevel=2
    )
    return list_categories(session=session)


def add_tag(feed_id: int, tag: str, session: Session | None = None) -> None:
    warnings.warn(
        "'add_tag' is deprecated, use 'set_feed_category' instead", DeprecationWarning, stacklevel=2
    )
    set_feed_category(feed_id, tag, session=session)


def remove_tag(feed_id: int, tag: str, session: Session | None = None) -> None:
    warnings.warn(
        "'remove_tag' is deprecated, use 'reset_feed_category' instead",
        DeprecationWarning,
        stacklevel=2,
    )
    reset_feed_category(feed_id, session=session)


def get_feeds_by_tag(tag: str, session: Session | None = None) -> list[Feed]:
    warnings.warn(
        "'get_feeds_by_tag' is deprecated, use 'get_feeds_by_category' instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return get_feeds_by_category(tag, session=session)


# --- Feed discovery (public wrapper) ---


def discover_feeds(url: str, timeout: int = 30) -> list[dict]:
    """Discover feed URLs from a website URL without subscribing.

    Returns list of {url, type, version, title, items_count}.
    """
    return _discover_feeds(url, timeout=timeout)


# --- OPML operations ---


def import_opml(file_path: str, session: Session | None = None) -> list[Feed]:
    """Import feeds from an OPML file. Returns list of added feeds."""
    from feedcli.opml import parse_opml

    outlines = parse_opml(file_path)
    feeds = []
    for outline in outlines:
        url = outline.get("xml_url") or outline.get("html_url")
        if not url:
            continue
        title = outline.get("title") or outline.get("text")
        category = outline.get("category")
        try:
            feed = add_feed(
                url=url,
                title=title,
                category=category,
                auto_discover=False,
                session=session,
            )
            feeds.append(feed)
        except FeedAlreadyExistsError:
            continue  # Duplicate — skip silently
        except ValueError as e:
            import logging

            logging.getLogger(__name__).warning("Skipping %s: %s", url, e)
            continue
    return feeds


def export_opml(file_path: str, session: Session | None = None) -> None:
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
    # VACUUM must run outside a transaction; AUTOCOMMIT ensures that.
    with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        conn.exec_driver_sql("VACUUM")


def db_backup(dest_path: str) -> None:
    """Backup the database to a file."""
    import os
    import shutil

    from feedcli.config import load_config

    config = load_config()
    src = config["db_path"]
    if src == ":memory:":
        raise ValueError("Cannot backup an in-memory database")
    if not os.path.exists(src):
        raise ValueError(
            f"Database file not found: {src}. Try running a command first to create the DB."
        )
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
    # Ensure the destination directory exists (e.g. on a fresh XDG setup).
    from pathlib import Path

    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dest)
    reset_engine()
