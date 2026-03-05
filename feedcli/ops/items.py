"""Item read, write, search, and star operations."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session, joinedload, selectinload

from feedcli.models import Item, ItemTag

from ._session import managed_session

log = logging.getLogger(__name__)


def get_unread_items(
    feed_id: int | None = None,
    tag: str | None = None,
    limit: int = 50,
    session: Session | None = None,
) -> list[Item]:
    """Get unread items, optionally filtered by feed or tag. Ordered by published_at desc."""
    with managed_session(session) as sess:
        query = (
            sess.query(Item)
            .options(joinedload(Item.feed), selectinload(Item.tags))
            .filter(Item.is_read == False, Item.deleted == False)  # noqa: E712
        )
        if feed_id is not None:
            query = query.filter(Item.feed_id == feed_id)
        if tag is not None:
            query = query.join(Item.tags).filter(ItemTag.name == tag)
        return query.order_by(Item.published_at.desc().nullslast()).limit(limit).all()


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
    with managed_session(session) as sess:
        query = (
            sess.query(Item)
            .options(joinedload(Item.feed), selectinload(Item.tags))
            .filter(Item.deleted == False)  # noqa: E712
        )
        if feed_id is not None:
            query = query.filter(Item.feed_id == feed_id)
        if tag is not None:
            query = query.join(Item.tags).filter(ItemTag.name == tag)
        if unread_only:
            query = query.filter(Item.is_read == False)  # noqa: E712
        if starred_only:
            query = query.filter(Item.is_starred == True)  # noqa: E712
        return (
            query.order_by(Item.published_at.desc().nullslast()).offset(offset).limit(limit).all()
        )


def get_item(item_id: int, session: Session | None = None) -> Item:
    """Get a single item by ID."""
    with managed_session(session) as sess:
        item = sess.query(Item).options(joinedload(Item.feed)).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        return item


def mark_read(item_id: int, session: Session | None = None) -> None:
    """Mark a single item as read."""
    with managed_session(session, commit=True) as sess:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        item.is_read = True


def mark_all_read(
    feed_id: int | None = None,
    session: Session | None = None,
) -> int:
    """Mark all items (or all items in a feed) as read. Returns count affected."""
    with managed_session(session, commit=True) as sess:
        query = sess.query(Item).filter(Item.is_read == False)  # noqa: E712
        if feed_id is not None:
            query = query.filter(Item.feed_id == feed_id)
        count = query.update({Item.is_read: True})
        return count


def mark_unread(item_id: int, session: Session | None = None) -> None:
    """Mark a single item as unread."""
    with managed_session(session, commit=True) as sess:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        item.is_read = False


def delete_item(item_id: int, hard: bool = False, session: Session | None = None) -> None:
    """Delete an item. Soft-delete by default (sets deleted=True), hard-delete removes from DB."""
    with managed_session(session, commit=True) as sess:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        if hard:
            sess.delete(item)
        else:
            item.deleted = True


def search_items(
    query: str,
    feed_id: int | None = None,
    tag: str | None = None,
    limit: int = 20,
    session: Session | None = None,
) -> list[Item]:
    """Full-text search across item titles and content."""
    with managed_session(session) as sess:
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
            q = q.join(Item.tags).filter(ItemTag.name == tag)
        return q.order_by(Item.published_at.desc().nullslast()).limit(limit).all()


def star_item(item_id: int, session: Session | None = None) -> None:
    """Star/bookmark an item."""
    with managed_session(session, commit=True) as sess:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        item.is_starred = True


def unstar_item(item_id: int, session: Session | None = None) -> None:
    """Remove star from an item."""
    with managed_session(session, commit=True) as sess:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")
        item.is_starred = False


def get_starred_items(
    limit: int = 50,
    session: Session | None = None,
) -> list[Item]:
    """Get all starred items."""
    with managed_session(session) as sess:
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


def get_item_url(item_id: int, session: Session | None = None) -> str:
    """Get just the URL for an item. Useful for opening in browser."""
    item = get_item(item_id, session=session)
    return item.url
