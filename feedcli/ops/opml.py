"""OPML import and export operations."""

from __future__ import annotations

import logging

from sqlalchemy.orm import Session

from .feeds import FeedAlreadyExistsError, add_feed, list_feeds

log = logging.getLogger(__name__)


def import_opml(file_path: str, session: Session | None = None) -> list["Feed"]:  # noqa: F821
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
            log.warning("Skipping %s: %s", url, e)
            continue
    return feeds


def export_opml(file_path: str, session: Session | None = None) -> None:
    """Export all feeds to an OPML file."""
    from feedcli.opml import generate_opml

    feeds = list_feeds(session=session)
    generate_opml(feeds, file_path)
