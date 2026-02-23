"""Tests for feedcli.discovery — feed URL discovery."""

import httpx
import respx

from feedcli.discovery import discover_feeds


class TestDiscoverFeeds:
    @respx.mock
    def test_direct_feed_url(self, sample_rss):
        """URL that is itself a feed should be returned directly."""
        respx.get("https://example.com/feed.xml").mock(
            return_value=httpx.Response(200, text=sample_rss)
        )
        result = discover_feeds("https://example.com/feed.xml")
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/feed.xml"
        assert result[0]["title"] == "Test Blog"

    @respx.mock
    def test_discover_from_html_link_tags(self, sample_page, sample_rss):
        """Should find feeds from <link> tags in HTML."""
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(200, text=sample_page)
        )
        respx.get("https://example.com/feed/rss.xml").mock(
            return_value=httpx.Response(200, text=sample_rss)
        )
        respx.get("https://example.com/feed/atom.xml").mock(
            return_value=httpx.Response(200, text=sample_rss)
        )
        result = discover_feeds("https://example.com/")
        assert len(result) >= 1
        urls = [r["url"] for r in result]
        assert "https://example.com/feed/rss.xml" in urls

    @respx.mock
    def test_no_feeds_found(self, sample_page_no_feeds):
        """Page with no feeds should return empty list."""
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(200, text=sample_page_no_feeds)
        )
        # Mock well-known and common endpoints to fail
        respx.route().mock(return_value=httpx.Response(404))
        result = discover_feeds("https://example.com/")
        assert len(result) == 0

    @respx.mock
    def test_discover_from_well_known_path(self, sample_rss):
        """Should fall back to well-known paths when HTML has no links."""
        html = "<html><head><title>No feeds</title></head><body></body></html>"
        respx.get("https://example.com/").mock(
            return_value=httpx.Response(200, text=html)
        )
        respx.get("https://example.com/feed.json").mock(
            return_value=httpx.Response(200, text=sample_rss)
        )
        # Stop further probing
        respx.route().mock(return_value=httpx.Response(404))
        result = discover_feeds("https://example.com/")
        assert len(result) == 1
        assert result[0]["url"] == "https://example.com/feed.json"

    @respx.mock
    def test_http_error_returns_empty(self):
        """Unreachable URL should return empty list."""
        respx.get("https://unreachable.example.com/").mock(
            side_effect=httpx.ConnectError("Connection refused")
        )
        result = discover_feeds("https://unreachable.example.com/")
        assert result == []
