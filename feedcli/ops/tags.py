"""Item tag CRUD operations."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from feedcli.models import Item, ItemTag

from ._session import managed_session

log = logging.getLogger(__name__)


def tag_item(item_id: int, tag: str, session: Session | None = None) -> None:
    """Add a tag to an item."""
    with managed_session(session, commit=True) as sess:
        item = sess.query(Item).filter(Item.id == item_id).first()
        if not item:
            raise ValueError(f"Item not found: {item_id}")

        existing = (
            sess.query(ItemTag).filter(ItemTag.item_id == item_id, ItemTag.name == tag).first()
        )
        if existing:
            return

        sess.add(ItemTag(item_id=item_id, name=tag))


def untag_item(item_id: int, tag: str, session: Session | None = None) -> None:
    """Remove a tag from an item."""
    with managed_session(session, commit=True) as sess:
        t = sess.query(ItemTag).filter(ItemTag.item_id == item_id, ItemTag.name == tag).first()
        if not t:
            raise ValueError(f"Tag '{tag}' not found on item {item_id}")

        sess.delete(t)


def list_item_tags(item_id: int | None = None, session: Session | None = None) -> list[str]:
    """List distinct tags, optionally filtered by item."""
    with managed_session(session) as sess:
        query = sess.query(ItemTag.name).distinct()
        if item_id is not None:
            query = query.filter(ItemTag.item_id == item_id)

        rows = query.order_by(ItemTag.name).all()
        return [row[0] for row in rows]


def get_items_by_tag(tag: str, limit: int = 50, session: Session | None = None) -> list[Item]:
    """Get items with a given tag."""
    from .items import get_items

    return get_items(tag=tag, limit=limit, session=session)


def delete_tag(tag: str, delete_items: bool = False, session: Session | None = None) -> None:
    """Delete a tag from all items. Optionally delete the associated items."""
    with managed_session(session, commit=True) as sess:
        if delete_items:
            item_ids = [
                row[0] for row in sess.query(ItemTag.item_id).filter(ItemTag.name == tag).all()
            ]
            if item_ids:
                sess.query(Item).filter(Item.id.in_(item_ids)).update(
                    {Item.deleted: True}, synchronize_session=False
                )

        sess.query(ItemTag).filter(ItemTag.name == tag).delete(synchronize_session=False)


def rename_tag(old_name: str, new_name: str, session: Session | None = None) -> None:
    """Rename a tag across all items."""
    with managed_session(session, commit=True) as sess:
        # To avoid unique constraint violations, only update tags where the item doesn't
        # already have the new tag. Then delete the remaining old tags.
        items_with_new = [
            row[0] for row in sess.query(ItemTag.item_id).filter(ItemTag.name == new_name).all()
        ]

        sess.query(ItemTag).filter(
            ItemTag.name == old_name, ~ItemTag.item_id.in_(items_with_new)
        ).update({ItemTag.name: new_name}, synchronize_session=False)
        sess.query(ItemTag).filter(ItemTag.name == old_name).delete(synchronize_session=False)
