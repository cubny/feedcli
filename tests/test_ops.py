"""Tests for feedcli.ops — high-level operations API."""

from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from feedcli.models import Feed, Item
from feedcli.ops import (
    add_feed,
    add_tag,
    delete_feed,
    delete_item,
    export_opml,
    get_feed,
    get_feeds_by_tag,
    get_item,
    get_item_url,
    get_items,
    get_starred_items,
    get_unread_items,
    import_opml,
    list_feeds,
    list_tags,
    mark_all_read,
    mark_read,
    mark_unread,
    remove_tag,
    search_items,
    star_item,
    unstar_item,
    update_feed,
)


@pytest.fixture
def feed_in_db(db_session):
    """Insert a feed directly into the test DB."""
    feed = Feed(url="https://example.com/feed.xml", title="Test Feed", created_at=datetime.now(timezone.utc))
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
            fetched_at=datetime.now(timezone.utc),
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
        from feedcli.ops import FeedAlreadyExistsError

        mock_discover.return_value = []
        add_feed("https://example.com/feed", auto_discover=False, session=db_session)
        # FeedAlreadyExistsError is a subclass of ValueError, so callers catching
        # ValueError still work; specific code can now catch FeedAlreadyExistsError.
        with pytest.raises(FeedAlreadyExistsError, match="already exists"):
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


class TestMarkUnread:
    def test_mark_unread(self, db_session, items_in_db):
        mark_read(items_in_db[0].id, session=db_session)
        assert get_item(items_in_db[0].id, session=db_session).is_read is True
        mark_unread(items_in_db[0].id, session=db_session)
        assert get_item(items_in_db[0].id, session=db_session).is_read is False

    def test_mark_unread_not_found(self, db_session):
        with pytest.raises(ValueError, match="Item not found"):
            mark_unread(999, session=db_session)


class TestDeleteItem:
    def test_soft_delete(self, db_session, items_in_db):
        delete_item(items_in_db[0].id, session=db_session)
        # Soft-deleted items should not appear in get_items
        items = get_items(session=db_session)
        assert len(items) == 2

    def test_hard_delete(self, db_session, items_in_db):
        delete_item(items_in_db[0].id, hard=True, session=db_session)
        with pytest.raises(ValueError, match="Item not found"):
            get_item(items_in_db[0].id, session=db_session)

    def test_delete_item_not_found(self, db_session):
        with pytest.raises(ValueError, match="Item not found"):
            delete_item(999, session=db_session)


class TestSearchItems:
    def test_search_by_title(self, db_session, items_in_db):
        results = search_items("Item 1", session=db_session)
        assert len(results) == 1
        assert results[0].title == "Item 1"

    def test_search_by_summary(self, db_session, items_in_db):
        results = search_items("Summary 2", session=db_session)
        assert len(results) == 1
        assert results[0].title == "Item 2"

    def test_search_no_results(self, db_session, items_in_db):
        results = search_items("nonexistent", session=db_session)
        assert len(results) == 0

    def test_search_case_insensitive(self, db_session, items_in_db):
        results = search_items("item 0", session=db_session)
        assert len(results) == 1

    def test_search_excludes_deleted(self, db_session, items_in_db):
        delete_item(items_in_db[0].id, session=db_session)
        results = search_items("Item", session=db_session)
        assert len(results) == 2

    def test_search_by_feed(self, db_session, items_in_db, feed_in_db):
        results = search_items("Item", feed_id=feed_in_db.id, session=db_session)
        assert len(results) == 3

    def test_search_limit(self, db_session, items_in_db):
        results = search_items("Item", limit=1, session=db_session)
        assert len(results) == 1


class TestStarItem:
    def test_star_item(self, db_session, items_in_db):
        star_item(items_in_db[0].id, session=db_session)
        item = get_item(items_in_db[0].id, session=db_session)
        assert item.is_starred is True

    def test_star_item_not_found(self, db_session):
        with pytest.raises(ValueError, match="Item not found"):
            star_item(999, session=db_session)


class TestUnstarItem:
    def test_unstar_item(self, db_session, items_in_db):
        star_item(items_in_db[0].id, session=db_session)
        unstar_item(items_in_db[0].id, session=db_session)
        item = get_item(items_in_db[0].id, session=db_session)
        assert item.is_starred is False

    def test_unstar_item_not_found(self, db_session):
        with pytest.raises(ValueError, match="Item not found"):
            unstar_item(999, session=db_session)


class TestGetStarredItems:
    def test_get_starred_items_empty(self, db_session, items_in_db):
        starred = get_starred_items(session=db_session)
        assert len(starred) == 0

    def test_get_starred_items(self, db_session, items_in_db):
        star_item(items_in_db[0].id, session=db_session)
        star_item(items_in_db[1].id, session=db_session)
        starred = get_starred_items(session=db_session)
        assert len(starred) == 2

    def test_get_starred_items_excludes_deleted(self, db_session, items_in_db):
        star_item(items_in_db[0].id, session=db_session)
        delete_item(items_in_db[0].id, session=db_session)
        starred = get_starred_items(session=db_session)
        assert len(starred) == 0

    def test_get_starred_items_limit(self, db_session, items_in_db):
        for item in items_in_db:
            star_item(item.id, session=db_session)
        starred = get_starred_items(limit=1, session=db_session)
        assert len(starred) == 1


class TestGetItemUrl:
    def test_get_item_url(self, db_session, items_in_db):
        url = get_item_url(items_in_db[0].id, session=db_session)
        assert url == "https://example.com/item-0"

    def test_get_item_url_not_found(self, db_session):
        with pytest.raises(ValueError, match="Item not found"):
            get_item_url(999, session=db_session)


class TestGetItemsStarredOnly:
    def test_get_items_starred_only(self, db_session, items_in_db):
        star_item(items_in_db[0].id, session=db_session)
        items = get_items(starred_only=True, session=db_session)
        assert len(items) == 1
        assert items[0].id == items_in_db[0].id

    def test_get_items_starred_only_empty(self, db_session, items_in_db):
        items = get_items(starred_only=True, session=db_session)
        assert len(items) == 0


class TestListTags:
    def test_list_tags_empty(self, db_session):
        tags = list_tags(session=db_session)
        assert tags == []

    def test_list_tags(self, db_session, feed_in_db):
        add_tag(feed_in_db.id, "tech", session=db_session)
        add_tag(feed_in_db.id, "ai", session=db_session)
        tags = list_tags(session=db_session)
        assert tags == ["ai", "tech"]  # sorted


class TestAddTag:
    def test_add_tag(self, db_session, feed_in_db):
        add_tag(feed_in_db.id, "tech", session=db_session)
        tags = list_tags(session=db_session)
        assert "tech" in tags

    def test_add_tag_duplicate_is_noop(self, db_session, feed_in_db):
        add_tag(feed_in_db.id, "tech", session=db_session)
        add_tag(feed_in_db.id, "tech", session=db_session)
        tags = list_tags(session=db_session)
        assert tags == ["tech"]

    def test_add_tag_feed_not_found(self, db_session):
        with pytest.raises(ValueError, match="Feed not found"):
            add_tag(999, "tech", session=db_session)


class TestRemoveTag:
    def test_remove_tag(self, db_session, feed_in_db):
        add_tag(feed_in_db.id, "tech", session=db_session)
        remove_tag(feed_in_db.id, "tech", session=db_session)
        tags = list_tags(session=db_session)
        assert tags == []

    def test_remove_tag_not_found(self, db_session, feed_in_db):
        with pytest.raises(ValueError, match="Tag .* not found"):
            remove_tag(feed_in_db.id, "nonexistent", session=db_session)


class TestGetFeedsByTag:
    def test_get_feeds_by_tag(self, db_session, feed_in_db):
        add_tag(feed_in_db.id, "tech", session=db_session)
        feeds = get_feeds_by_tag("tech", session=db_session)
        assert len(feeds) == 1
        assert feeds[0].id == feed_in_db.id

    def test_get_feeds_by_tag_empty(self, db_session, feed_in_db):
        feeds = get_feeds_by_tag("nonexistent", session=db_session)
        assert feeds == []


class TestImportExportOpml:
    @patch("feedcli.ops._discover_feeds")
    def test_export_and_import(self, mock_discover, db_session, tmp_path):
        mock_discover.return_value = []
        # Create a feed
        feed = add_feed(
            "https://example.com/feed.xml",
            title="Test Feed",
            auto_discover=False,
            session=db_session,
        )
        add_tag(feed.id, "tech", session=db_session)

        # Export
        opml_file = str(tmp_path / "feeds.opml")
        export_opml(opml_file, session=db_session)

        # Delete the feed
        delete_feed(feed.id, session=db_session)
        assert list_feeds(session=db_session) == []

        # Import
        imported = import_opml(opml_file, session=db_session)
        assert len(imported) == 1
        assert imported[0].url == "https://example.com/feed.xml"

    @patch("feedcli.ops._discover_feeds")
    def test_import_opml_skips_duplicates(self, mock_discover, db_session, tmp_path):
        """Duplicate feeds are silently skipped, not raised."""
        mock_discover.return_value = []
        feed = add_feed(
            "https://example.com/feed.xml",
            title="Test Feed",
            auto_discover=False,
            session=db_session,
        )
        opml_file = str(tmp_path / "feeds.opml")
        export_opml(opml_file, session=db_session)

        # Import again — duplicate should be skipped, not raise
        imported = import_opml(opml_file, session=db_session)
        assert len(imported) == 0  # already exists

        # Only one feed in DB
        assert len(list_feeds(session=db_session)) == 1


class TestResetFeedErrors:
    @patch("feedcli.ops._discover_feeds")
    def test_reset_feed_errors(self, mock_discover, db_session, feed_in_db):
        from feedcli.ops import reset_feed_errors

        mock_discover.return_value = []
        # Simulate an error state
        feed = db_session.get(feed_in_db.__class__, feed_in_db.id)
        feed.error_count = 5
        feed.disabled = True
        feed.last_error = "timeout"
        db_session.commit()

        # fetch_feed is imported at the top of feedcli/ops.py, so patching
        # feedcli.ops.fetch_feed correctly intercepts calls from update_feed.
        with patch("feedcli.ops.fetch_feed", return_value=0):
            reset_feed_errors(feed_in_db.id, session=db_session)

        from feedcli.models import Feed as FeedModel

        updated = db_session.get(FeedModel, feed_in_db.id)
        assert updated.error_count == 0
        assert updated.disabled is False
        assert updated.last_error is None

    def test_reset_feed_errors_not_found(self, db_session):
        from feedcli.ops import reset_feed_errors

        with pytest.raises(ValueError, match="Feed not found"):
            reset_feed_errors(999, session=db_session)


class TestSearchItemsWildcardEscaping:
    def test_percent_is_escaped(self, db_session, items_in_db, feed_in_db):
        """A literal % in the query should not act as a wildcard."""
        # None of the test items have '%' in their titles
        results = search_items("100%", session=db_session)
        assert len(results) == 0

    def test_underscore_is_escaped(self, db_session, items_in_db):
        """A literal _ in the query should not act as a wildcard."""
        # 'Item_0' pattern should not match 'Item 0' (space, not underscore)
        results = search_items("Item_0", session=db_session)
        assert len(results) == 0


class TestSaveConfig:
    def test_save_config_creates_file(self, tmp_path, monkeypatch):
        from feedcli.config import save_config

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_config("database.path", "/tmp/test.db")

        from feedcli.config import get_config_path

        config_path = get_config_path()
        assert config_path.exists()
        content = config_path.read_text()
        assert "test.db" in content

    def test_write_toml_raises_on_deep_nesting(self, tmp_path):
        from feedcli.config import _write_toml
        from pathlib import Path

        path = tmp_path / "config.toml"
        with pytest.raises(ValueError, match="nested too deeply"):
            _write_toml({"a": {"b": {"c": "deep"}}}, path)
