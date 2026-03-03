"""Tests for feedcli.cli — Click CLI commands."""

import json
from datetime import datetime
from unittest.mock import patch

from click.testing import CliRunner
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from feedcli.cli import main
from feedcli.models import Base, Feed, Item


def _make_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    return sessionmaker(bind=engine)()


class TestFeedsCLI:
    @patch("feedcli.cli.get_session")
    @patch("feedcli.ops._discover_feeds")
    def test_feeds_add(self, mock_discover, mock_get_session):
        session = _make_session()
        mock_get_session.return_value = session
        mock_discover.return_value = []

        runner = CliRunner()
        result = runner.invoke(
            main, ["feeds", "add", "https://example.com/feed.xml", "--no-discover"]
        )
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["url"] == "https://example.com/feed.xml"

    @patch("feedcli.cli.get_session")
    def test_feeds_list_empty(self, mock_get_session):
        session = _make_session()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["feeds", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []

    @patch("feedcli.cli.get_session")
    def test_feeds_list_with_feed(self, mock_get_session):
        session = _make_session()
        feed = Feed(url="https://example.com/rss", title="Test", created_at=datetime.utcnow())
        session.add(feed)
        session.commit()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["feeds", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["url"] == "https://example.com/rss"

    @patch("feedcli.cli.get_session")
    def test_feeds_delete(self, mock_get_session):
        session = _make_session()
        feed = Feed(url="https://example.com/rss", title="Test", created_at=datetime.utcnow())
        session.add(feed)
        session.commit()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["feeds", "delete", str(feed.id), "--force"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "deleted"


class TestItemsCLI:
    @patch("feedcli.cli.get_session")
    def test_items_list_empty(self, mock_get_session):
        session = _make_session()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["items", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data == []

    @patch("feedcli.cli.get_session")
    def test_items_list_with_items(self, mock_get_session):
        session = _make_session()
        feed = Feed(url="https://example.com/rss", title="Test", created_at=datetime.utcnow())
        session.add(feed)
        session.flush()
        item = Item(
            feed_id=feed.id,
            guid="g1",
            title="Item 1",
            url="https://example.com/1",
            summary="Summary",
            published_at=datetime(2024, 1, 1),
            fetched_at=datetime.utcnow(),
            is_read=False,
        )
        session.add(item)
        session.commit()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["items", "list"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["title"] == "Item 1"

    @patch("feedcli.cli.get_session")
    def test_items_show(self, mock_get_session):
        session = _make_session()
        feed = Feed(url="https://example.com/rss", title="Test", created_at=datetime.utcnow())
        session.add(feed)
        session.flush()
        item = Item(
            feed_id=feed.id,
            guid="g1",
            title="Item 1",
            url="https://example.com/1",
            summary="Summary",
            content="Full content",
            published_at=datetime(2024, 1, 1),
            fetched_at=datetime.utcnow(),
            is_read=False,
        )
        session.add(item)
        session.commit()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["items", "show", str(item.id)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["title"] == "Item 1"
        assert data["content"] == "Full content"

    @patch("feedcli.cli.get_session")
    def test_items_mark_read(self, mock_get_session):
        session = _make_session()
        feed = Feed(url="https://example.com/rss", title="Test", created_at=datetime.utcnow())
        session.add(feed)
        session.flush()
        item = Item(
            feed_id=feed.id,
            guid="g1",
            title="Item 1",
            url="https://example.com/1",
            fetched_at=datetime.utcnow(),
            is_read=False,
        )
        session.add(item)
        session.commit()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["items", "mark-read", str(item.id)])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["status"] == "ok"

    @patch("feedcli.cli.get_session")
    def test_items_mark_read_all(self, mock_get_session):
        session = _make_session()
        feed = Feed(url="https://example.com/rss", title="Test", created_at=datetime.utcnow())
        session.add(feed)
        session.flush()
        for i in range(3):
            session.add(
                Item(
                    feed_id=feed.id,
                    guid=f"g{i}",
                    title=f"Item {i}",
                    fetched_at=datetime.utcnow(),
                    is_read=False,
                )
            )
        session.commit()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["items", "mark-read", "--all"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert data["marked_read"] == 3

    @patch("feedcli.cli.get_session")
    def test_items_list_unread(self, mock_get_session):
        session = _make_session()
        feed = Feed(url="https://example.com/rss", title="Test", created_at=datetime.utcnow())
        session.add(feed)
        session.flush()
        session.add(
            Item(
                feed_id=feed.id,
                guid="g1",
                title="Unread",
                fetched_at=datetime.utcnow(),
                is_read=False,
            )
        )
        session.add(
            Item(
                feed_id=feed.id,
                guid="g2",
                title="Read",
                fetched_at=datetime.utcnow(),
                is_read=True,
            )
        )
        session.commit()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["items", "list", "--unread"])
        assert result.exit_code == 0
        data = json.loads(result.output)
        assert len(data) == 1
        assert data[0]["title"] == "Unread"

    @patch("feedcli.cli.get_session")
    def test_output_format_table(self, mock_get_session):
        session = _make_session()
        mock_get_session.return_value = session

        runner = CliRunner()
        result = runner.invoke(main, ["feeds", "list", "--format", "table"])
        assert result.exit_code == 0
        assert "No results." in result.output
