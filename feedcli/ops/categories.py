"""Category CRUD operations."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from feedcli.models import Category, Feed

from ._session import managed_session

log = logging.getLogger(__name__)


def list_categories(session: Session | None = None) -> list[str]:
    """List all categories in use."""
    with managed_session(session) as sess:
        rows = sess.query(Category.name).distinct().order_by(Category.name).all()
        return [row[0] for row in rows]


def create_category(name: str, session: Session | None = None) -> None:
    """Create a new category."""
    with managed_session(session, commit=True) as sess:
        existing = sess.query(Category).filter(Category.name == name).first()
        if existing:
            return
        sess.add(Category(name=name))


def delete_category(name: str, move_to: str = "default", session: Session | None = None) -> None:
    """Delete a category and move its feeds to another category."""
    if name == "default":
        raise ValueError("Cannot delete the default category")
    with managed_session(session, commit=True) as sess:
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


def rename_category(old_name: str, new_name: str, session: Session | None = None) -> None:
    """Rename a category."""
    if old_name == "default":
        raise ValueError("Cannot rename the default category")
    with managed_session(session, commit=True) as sess:
        cat = sess.query(Category).filter(Category.name == old_name).first()
        if not cat:
            raise ValueError(f"Category not found: {old_name}")

        existing_new = sess.query(Category).filter(Category.name == new_name).first()
        if existing_new:
            raise ValueError(f"Category already exists: {new_name}")

        cat.name = new_name


def set_feed_category(feed_id: int, name: str, session: Session | None = None) -> None:
    """Set the category for a feed."""
    with managed_session(session, commit=True) as sess:
        feed = sess.query(Feed).filter(Feed.id == feed_id).first()
        if not feed:
            raise ValueError(f"Feed not found: {feed_id}")

        cat = sess.query(Category).filter(Category.name == name).first()
        if not cat:
            cat = Category(name=name)
            sess.add(cat)
            sess.flush()

        feed.category_id = cat.id


def reset_feed_category(feed_id: int, session: Session | None = None) -> None:
    """Reset a feed's category to 'default'."""
    set_feed_category(feed_id, "default", session=session)


def get_feeds_by_category(name: str, session: Session | None = None) -> list[Feed]:
    """Get all feeds with a given category."""
    from .feeds import list_feeds

    return list_feeds(category=name, session=session)
