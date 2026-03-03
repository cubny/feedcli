"""Tests for feedcli.ops — high-level operations API."""

import signal
from datetime import datetime, timezone
from unittest.mock import patch

import pytest

from feedcli.models import Feed, Item
from feedcli.ops import (
    add_feed,
    delete_feed,
    delete_item,
    export_opml,
    get_item,
    get_item_url,
    get_items,
    get_starred_items,
    get_unread_items,
    import_opml,
    list_feeds,
    mark_all_read,
    mark_read,
    mark_unread,
    search_items,
    star_item,
    unstar_item,
    update_feed,
)


@pytest.fixture
def feed_in_db(db_session):
    """Insert a feed directly into the test DB."""
    feed = Feed(
        url="https://example.com/feed.xml", title="Test Feed", created_at=datetime.now(timezone.utc)
    )
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


class TestCategories:
    def test_list_categories_empty(self, db_session):
        from feedcli.ops import list_categories

        assert list_categories(session=db_session) == ["default"]

    def test_create_category(self, db_session):
        from feedcli.ops import create_category, list_categories

        create_category("tech", session=db_session)
        cats = list_categories(session=db_session)
        assert "tech" in cats

    def test_set_feed_category(self, db_session, feed_in_db):
        from feedcli.ops import get_feed, set_feed_category

        set_feed_category(feed_in_db.id, "ai", session=db_session)
        feed = get_feed(feed_in_db.id, session=db_session)
        assert feed.category.name == "ai"

    def test_reset_feed_category(self, db_session, feed_in_db):
        from feedcli.ops import get_feed, reset_feed_category, set_feed_category

        set_feed_category(feed_in_db.id, "ai", session=db_session)
        reset_feed_category(feed_in_db.id, session=db_session)
        feed = get_feed(feed_in_db.id, session=db_session)
        assert feed.category.name == "default"

    def test_get_feeds_by_category(self, db_session, feed_in_db):
        from feedcli.ops import get_feeds_by_category, set_feed_category

        set_feed_category(feed_in_db.id, "ai", session=db_session)
        feeds = get_feeds_by_category("ai", session=db_session)
        assert len(feeds) == 1
        assert feeds[0].id == feed_in_db.id

    def test_delete_category(self, db_session, feed_in_db):
        from feedcli.ops import delete_category, get_feed, set_feed_category

        set_feed_category(feed_in_db.id, "temp", session=db_session)
        delete_category("temp", session=db_session)
        feed = get_feed(feed_in_db.id, session=db_session)
        assert feed.category.name == "default"

    def test_rename_category(self, db_session, feed_in_db):
        from feedcli.ops import get_feed, rename_category, set_feed_category

        set_feed_category(feed_in_db.id, "old", session=db_session)
        rename_category("old", "new", session=db_session)
        feed = get_feed(feed_in_db.id, session=db_session)
        assert feed.category.name == "new"


class TestItemTags:
    def test_tag_item(self, db_session, items_in_db):
        from feedcli.ops import list_item_tags, tag_item

        tag_item(items_in_db[0].id, "read-later", session=db_session)
        tags = list_item_tags(item_id=items_in_db[0].id, session=db_session)
        assert tags == ["read-later"]

    def test_tag_item_duplicate_noop(self, db_session, items_in_db):
        from feedcli.ops import list_item_tags, tag_item

        tag_item(items_in_db[0].id, "read-later", session=db_session)
        tag_item(items_in_db[0].id, "read-later", session=db_session)
        tags = list_item_tags(item_id=items_in_db[0].id, session=db_session)
        assert tags == ["read-later"]

    def test_untag_item(self, db_session, items_in_db):
        from feedcli.ops import list_item_tags, tag_item, untag_item

        tag_item(items_in_db[0].id, "read-later", session=db_session)
        untag_item(items_in_db[0].id, "read-later", session=db_session)
        assert list_item_tags(item_id=items_in_db[0].id, session=db_session) == []

    def test_get_items_by_tag(self, db_session, items_in_db):
        from feedcli.ops import get_items_by_tag, tag_item

        tag_item(items_in_db[0].id, "urgent", session=db_session)
        items = get_items_by_tag("urgent", session=db_session)
        assert len(items) == 1
        assert items[0].id == items_in_db[0].id

    def test_delete_tag(self, db_session, items_in_db):
        from feedcli.ops import delete_tag, get_items_by_tag, list_item_tags, tag_item

        tag_item(items_in_db[0].id, "temp", session=db_session)
        delete_tag("temp", session=db_session)
        assert list_item_tags(session=db_session) == []
        assert get_items_by_tag("temp", session=db_session) == []

    def test_delete_tag_with_items(self, db_session, items_in_db):
        from feedcli.ops import delete_tag, tag_item

        tag_item(items_in_db[0].id, "delete-me", session=db_session)
        delete_tag("delete-me", delete_items=True, session=db_session)
        from feedcli.models import Item

        item = db_session.get(Item, items_in_db[0].id)
        assert item.deleted is True

    def test_rename_tag(self, db_session, items_in_db):
        from feedcli.ops import list_item_tags, rename_tag, tag_item

        tag_item(items_in_db[0].id, "old-tag", session=db_session)
        rename_tag("old-tag", "new-tag", session=db_session)
        assert list_item_tags(session=db_session) == ["new-tag"]


class TestImportExportOpml:
    @patch("feedcli.ops._discover_feeds")
    def test_export_and_import(self, mock_discover, db_session, tmp_path):
        mock_discover.return_value = []
        # Create a feed
        feed = add_feed(
            "https://example.com/feed.xml",
            title="Test Feed",
            category="tech",
            auto_discover=False,
            session=db_session,
        )
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
        add_feed(
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

        path = tmp_path / "config.toml"
        with pytest.raises(ValueError, match="nested too deeply"):
            _write_toml({"a": {"b": {"c": "deep"}}}, path)

    def test_toml_value_escapes_backslash_and_quote(self):
        from feedcli.config import _toml_value

        assert _toml_value("C:\\Users\\foo") == '"C:\\\\Users\\\\foo"'
        assert _toml_value('say "hello"') == '"say \\"hello\\""'

    def test_save_config_stores_int_for_numeric_keys(self, tmp_path, monkeypatch):
        from feedcli.config import save_config

        monkeypatch.setenv("XDG_CONFIG_HOME", str(tmp_path))
        save_config("fetch.timeout", "42")

        from feedcli.config import get_config_path

        content = get_config_path().read_text()
        # Should be bare integer, not quoted string
        assert "timeout = 42" in content
        assert 'timeout = "42"' not in content


class TestDbOps:
    def test_db_backup_missing_source_raises(self, tmp_path, monkeypatch):
        from feedcli.ops import db_backup

        monkeypatch.setenv("FEEDCLI_DB_PATH", str(tmp_path / "nonexistent.db"))
        with pytest.raises(ValueError, match="Database file not found"):
            db_backup(str(tmp_path / "out.db"))

    def test_db_backup_in_memory_raises(self, monkeypatch):
        from feedcli.ops import db_backup

        monkeypatch.setenv("FEEDCLI_DB_PATH", ":memory:")
        with pytest.raises(ValueError, match="in-memory"):
            db_backup("/tmp/out.db")

    def test_db_restore_missing_source_raises(self, tmp_path, monkeypatch):
        from feedcli.ops import db_restore

        monkeypatch.setenv("FEEDCLI_DB_PATH", str(tmp_path / "feedcli.db"))
        with pytest.raises(ValueError, match="Backup file not found"):
            db_restore(str(tmp_path / "nonexistent.db"))

    def test_db_restore_in_memory_raises(self, tmp_path, monkeypatch):
        from feedcli.ops import db_restore

        monkeypatch.setenv("FEEDCLI_DB_PATH", ":memory:")
        src = tmp_path / "backup.db"
        src.write_bytes(b"")
        with pytest.raises(ValueError, match="in-memory"):
            db_restore(str(src))

    def test_db_backup_restore_roundtrip(self, tmp_path, monkeypatch):
        from feedcli.db import reset_engine
        from feedcli.ops import db_backup, db_restore

        db_path = tmp_path / "feedcli.db"
        backup_path = tmp_path / "backup.db"
        monkeypatch.setenv("FEEDCLI_DB_PATH", str(db_path))
        reset_engine()

        # Create the DB by listing feeds
        list_feeds(session=None)

        db_backup(str(backup_path))
        assert backup_path.exists()
        db_restore(str(backup_path))
        # Engine is reset; verify DB is still valid
        assert list_feeds(session=None) == []

    def test_db_restore_creates_dest_dir(self, tmp_path, monkeypatch):
        from feedcli.db import reset_engine
        from feedcli.ops import db_restore

        src = tmp_path / "backup.db"
        src.write_bytes(b"SQLite format 3\x00")
        nested_dest = tmp_path / "a" / "b" / "feedcli.db"
        monkeypatch.setenv("FEEDCLI_DB_PATH", str(nested_dest))
        reset_engine()
        # Should not raise FileNotFoundError for missing parent dirs
        db_restore(str(src))
        assert nested_dest.exists()


class TestDaemon:
    def test_status_not_running_no_pidfile(self, tmp_path, monkeypatch):
        from feedcli.daemon import status

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        result = status()
        assert result == {"running": False}

    def test_status_stale_pidfile(self, tmp_path, monkeypatch):
        from feedcli.daemon import status

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        pid_file = tmp_path / "feedcli" / "daemon.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        # Write a PID that definitely doesn't exist
        pid_file.write_text("999999")
        result = status()
        assert result["running"] is False
        assert not pid_file.exists()

    def test_status_corrupt_pidfile(self, tmp_path, monkeypatch):
        from feedcli.daemon import status

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        pid_file = tmp_path / "feedcli" / "daemon.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("not-a-number")
        result = status()
        assert result["running"] is False
        assert not pid_file.exists()

    def test_stop_not_running_raises(self, tmp_path, monkeypatch):
        from feedcli.daemon import stop

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        with pytest.raises(RuntimeError, match="not running"):
            stop()

    def test_stop_corrupt_pidfile_raises(self, tmp_path, monkeypatch):
        from feedcli.daemon import stop

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        pid_file = tmp_path / "feedcli" / "daemon.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("not-a-number")
        with pytest.raises(RuntimeError, match="corrupt"):
            stop()

    def test_stop_sends_sigterm(self, tmp_path, monkeypatch):
        from unittest.mock import patch

        from feedcli.daemon import stop

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        pid_file = tmp_path / "feedcli" / "daemon.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("12345")
        with patch("feedcli.daemon.os.kill") as mock_kill:
            stop()
        mock_kill.assert_called_once_with(12345, signal.SIGTERM)

    def test_stop_permission_error_raises(self, tmp_path, monkeypatch):
        from unittest.mock import patch

        from feedcli.daemon import stop

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        pid_file = tmp_path / "feedcli" / "daemon.pid"
        pid_file.parent.mkdir(parents=True, exist_ok=True)
        pid_file.write_text("12345")
        with patch("feedcli.daemon.os.kill", side_effect=PermissionError):
            with pytest.raises(RuntimeError, match="permission denied"):
                stop()

    def test_logs_no_logfile(self, tmp_path, monkeypatch):
        from feedcli.daemon import logs

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        assert logs() == "No log file found."

    def test_logs_returns_last_n_lines(self, tmp_path, monkeypatch):
        from feedcli.daemon import logs

        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path))
        log_file = tmp_path / "feedcli" / "daemon.log"
        log_file.parent.mkdir(parents=True, exist_ok=True)
        log_file.write_text("\n".join(f"line {i}" for i in range(100)))
        result = logs(lines=10)
        assert "line 99" in result
        assert "line 0" not in result
