"""Tests for feedcli.ops — high-level operations API."""

from datetime import datetime
from unittest.mock import patch

import pytest

from feedcli.models import Feed, Item
from feedcli.ops import (
    add_feed,
    delete_feed,
    get_item,
    get_items,
    get_unread_items,
    list_feeds,
    mark_all_read,
    mark_read,
    update_feed,
)


@pytest.fixture
def feed_in_db(db_session):
    """Insert a feed directly into the test DB."""
    feed = Feed(url="https://example.com/feed.xml", title="Test Feed", created_at=datetime.utcnow())
    db_session.add(feed)
    db_session.commit()
    return feed


@pytest.fixture
def items_in_db(db_session, feed_in_db):
    """Insert items into the test DB."""
    items = []
    for i in range(3):
        item = Item(
            feed_id=feed_in_db.id,
            guid=f"guid-{i}",
            title=f"Item {i}",
            url=f"https://example.com/item-{i}",
            summary=f"Summary {i}",
            published_at=datetime(2024, 1, i + 1),
            fetched_at=datetime.utcnow(),
            is_read=False,
        )
        db_session.add(item)
        items.append(item)
    db_session.commit()
    return items


class TestAddFeed:
    @patch("feedcli.ops._discover_feeds")
    def test_add_feed_with_discovery(self, mock_discover, db_session):
        mock_discover.return_value = [
            {"url": "https://blog.example.com/feed.xml", "type": "rss20", "title": "Blog Feed"}
        ]
        feed = add_feed("https://blog.example.com", session=db_session)
        assert feed.url == "https://blog.example.com/feed.xml"
        assert feed.title == "Blog Feed"
        assert feed.website == "https://blog.example.com"

    @patch("feedcli.ops._discover_feeds")
    def test_add_feed_no_discovery(self, mock_discover, db_session):
        mock_discover.return_value = []
        feed = add_feed("https://example.com/rss.xml", auto_discover=False, session=db_session)
        assert feed.url == "https://example.com/rss.xml"
        mock_discover.assert_not_called()

    @patch("feedcli.ops._discover_feeds")
    def test_add_feed_custom_title(self, mock_discover, db_session):
        mock_discover.return_value = []
        feed = add_feed(
            "https://example.com/feed", title="My Feed", auto_discover=False, session=db_session
        )
        assert feed.title == "My Feed"

    @patch("feedcli.ops._discover_feeds")
    def test_add_feed_duplicate_raises(self, mock_discover, db_session):
        mock_discover.return_value = []
        add_feed("https://example.com/feed", auto_discover=False, session=db_session)
        with pytest.raises(ValueError, match="already exists"):
            add_feed("https://example.com/feed", auto_discover=False, session=db_session)


class TestListFeeds:
    def test_list_feeds_empty(self, db_session):
        feeds = list_feeds(session=db_session)
        assert feeds == []

    def test_list_feeds(self, db_session, feed_in_db):
        feeds = list_feeds(session=db_session)
        assert len(feeds) == 1
        assert feeds[0].url == "https://example.com/feed.xml"


class TestDeleteFeed:
    def test_delete_feed(self, db_session, feed_in_db):
        delete_feed(feed_in_db.id, session=db_session)
        feeds = list_feeds(session=db_session)
        assert feeds == []

    def test_delete_feed_not_found(self, db_session):
        with pytest.raises(ValueError, match="Feed not found"):
            delete_feed(999, session=db_session)


class TestGetUnreadItems:
    def test_get_unread_items(self, db_session, items_in_db):
        unread = get_unread_items(session=db_session)
        assert len(unread) == 3

    def test_get_unread_items_after_mark_read(self, db_session, items_in_db):
        mark_read(items_in_db[0].id, session=db_session)
        unread = get_unread_items(session=db_session)
        assert len(unread) == 2

    def test_get_unread_items_by_feed(self, db_session, items_in_db, feed_in_db):
        unread = get_unread_items(feed_id=feed_in_db.id, session=db_session)
        assert len(unread) == 3

    def test_get_unread_items_limit(self, db_session, items_in_db):
        unread = get_unread_items(limit=1, session=db_session)
        assert len(unread) == 1


class TestMarkRead:
    def test_mark_read(self, db_session, items_in_db):
        mark_read(items_in_db[0].id, session=db_session)
        item = get_item(items_in_db[0].id, session=db_session)
        assert item.is_read is True

    def test_mark_read_not_found(self, db_session):
        with pytest.raises(ValueError, match="Item not found"):
            mark_read(999, session=db_session)


class TestMarkAllRead:
    def test_mark_all_read(self, db_session, items_in_db):
        count = mark_all_read(session=db_session)
        assert count == 3
        unread = get_unread_items(session=db_session)
        assert len(unread) == 0

    def test_mark_all_read_by_feed(self, db_session, items_in_db, feed_in_db):
        count = mark_all_read(feed_id=feed_in_db.id, session=db_session)
        assert count == 3


class TestGetItems:
    def test_get_items(self, db_session, items_in_db):
        items = get_items(session=db_session)
        assert len(items) == 3

    def test_get_items_unread_only(self, db_session, items_in_db):
        mark_read(items_in_db[0].id, session=db_session)
        items = get_items(unread_only=True, session=db_session)
        assert len(items) == 2


class TestUpdateFeed:
    @patch("feedcli.ops.fetch_feed")
    def test_update_feed(self, mock_fetch, db_session, feed_in_db):
        mock_fetch.return_value = 5
        count = update_feed(feed_in_db.id, session=db_session)
        assert count == 5
        mock_fetch.assert_called_once()

    def test_update_feed_not_found(self, db_session):
        with pytest.raises(ValueError, match="Feed not found"):
            update_feed(999, session=db_session)
