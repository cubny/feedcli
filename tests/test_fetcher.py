"""Tests for feedcli.fetcher — feed fetching and parsing."""

from datetime import datetime, timezone

import httpx
import pytest
import respx

from feedcli.fetcher import fetch_feed
from feedcli.models import Feed, Item


@pytest.fixture
def feed(db_session):
    """Create a feed in the test DB."""
    f = Feed(
        url="https://example.com/feed.xml", title="Test Feed", created_at=datetime.now(timezone.utc)
    )
    db_session.add(f)
    db_session.commit()
    return f


class TestFetchFeed:
    @respx.mock
    def test_fetch_rss_items(self, db_session, feed, sample_rss):
        respx.get("https://example.com/feed.xml").mock(
            return_value=httpx.Response(200, text=sample_rss)
        )
        count = fetch_feed(feed, db_session)
        assert count == 2
        items = db_session.query(Item).filter(Item.feed_id == feed.id).all()
        assert len(items) == 2
        titles = {i.title for i in items}
        assert "First Post" in titles
        assert "Second Post" in titles

    @respx.mock
    def test_fetch_atom_items(self, db_session, feed, sample_atom):
        respx.get("https://example.com/feed.xml").mock(
            return_value=httpx.Response(200, text=sample_atom)
        )
        count = fetch_feed(feed, db_session)
        assert count == 2
        items = db_session.query(Item).filter(Item.feed_id == feed.id).all()
        # Check that content is populated from Atom content
        entry_one = next(i for i in items if i.title == "Atom Entry One")
        assert entry_one.summary == "Short summary of entry one"
        assert "<p>Full content of entry one</p>" in entry_one.content

    @respx.mock
    def test_deduplication(self, db_session, feed, sample_rss):
        respx.get("https://example.com/feed.xml").mock(
            return_value=httpx.Response(200, text=sample_rss)
        )
        # Fetch twice
        count1 = fetch_feed(feed, db_session)
        count2 = fetch_feed(feed, db_session)
        assert count1 == 2
        assert count2 == 0
        items = db_session.query(Item).filter(Item.feed_id == feed.id).all()
        assert len(items) == 2

    @respx.mock
    def test_conditional_get_304(self, db_session, feed):
        feed.etag = '"abc123"'
        db_session.commit()

        respx.get("https://example.com/feed.xml").mock(return_value=httpx.Response(304))
        count = fetch_feed(feed, db_session)
        assert count == 0
        assert feed.last_error is None
        assert feed.error_count == 0

    @respx.mock
    def test_http_error_records_error(self, db_session, feed):
        respx.get("https://example.com/feed.xml").mock(return_value=httpx.Response(500))
        count = fetch_feed(feed, db_session)
        assert count == 0
        assert feed.last_error == "HTTP 500"
        assert feed.error_count == 1

    @respx.mock
    def test_network_error_records_error(self, db_session, feed):
        respx.get("https://example.com/feed.xml").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        count = fetch_feed(feed, db_session)
        assert count == 0
        assert feed.error_count == 1
        assert "Connection refused" in feed.last_error

    @respx.mock
    def test_updates_etag_and_last_modified(self, db_session, feed, sample_rss):
        respx.get("https://example.com/feed.xml").mock(
            return_value=httpx.Response(
                200,
                text=sample_rss,
                headers={"etag": '"xyz789"', "last-modified": "Mon, 01 Jan 2024 00:00:00 GMT"},
            )
        )
        fetch_feed(feed, db_session)
        assert feed.etag == '"xyz789"'
        assert feed.last_modified == "Mon, 01 Jan 2024 00:00:00 GMT"

    @respx.mock
    def test_updates_feed_title_from_parsed(self, db_session, sample_rss):
        """Feed with no title gets title from parsed feed."""
        f = Feed(
            url="https://example.com/feed2.xml", title=None, created_at=datetime.now(timezone.utc)
        )
        db_session.add(f)
        db_session.commit()

        respx.get("https://example.com/feed2.xml").mock(
            return_value=httpx.Response(200, text=sample_rss)
        )
        fetch_feed(f, db_session)
        assert f.title == "Test Blog"

    @respx.mock
    def test_invalid_feed_records_error(self, db_session, feed):
        respx.get("https://example.com/feed.xml").mock(
            return_value=httpx.Response(200, text="<html><body>Not a feed</body></html>")
        )
        count = fetch_feed(feed, db_session)
        assert count == 0
        assert feed.last_error == "Failed to parse feed"
