"""Deprecated aliases for old Tag-on-Feed API (replaced by categories)."""

from __future__ import annotations

import warnings

from sqlalchemy.orm import Session

from feedcli.models import Feed

from .categories import (
    get_feeds_by_category,
    list_categories,
    reset_feed_category,
    set_feed_category,
)


def list_tags(session: Session | None = None) -> list[str]:
    warnings.warn(
        "'list_tags' is deprecated, use 'list_categories' instead",
        DeprecationWarning,
        stacklevel=2,
    )
    return list_categories(session=session)


def add_tag(feed_id: int, tag: str, session: Session | None = None) -> None:
    warnings.warn(
        "'add_tag' is deprecated, use 'set_feed_category' instead",
        DeprecationWarning,
        stacklevel=2,
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
