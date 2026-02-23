"""feedcli skill tools — callable by AI agents.

Each function returns a plain string suitable for LLM consumption.
feedcli must be pip install -e'd in the same Python environment.
"""

from feedcli.ops import (
    add_feed,
    delete_feed,
    get_items,
    get_unread_items,
    list_feeds,
    mark_all_read,
    mark_read,
    update_all_feeds,
)


def feeds_get_unread(limit: int = 50) -> str:
    """Get unread feed items for digest processing.
    Returns titles, summaries, feed names, and item IDs.
    limit: max number of items to return (default 50)
    """
    items = get_unread_items(limit=limit)
    if not items:
        return "No unread items."
    lines = []
    for item in items:
        feed_title = item.feed.title if item.feed else "Unknown"
        lines.append(f"[{item.id}] {feed_title} | {item.title}")
        if item.summary:
            lines.append(f"  {item.summary[:300]}")
        if item.url:
            lines.append(f"  {item.url}")
        lines.append("")
    return "\n".join(lines)


def feeds_mark_read(item_ids: str) -> str:
    """Mark items as read after digest processing.
    item_ids: comma-separated item IDs
    """
    ids = [int(x.strip()) for x in item_ids.split(",") if x.strip()]
    for item_id in ids:
        mark_read(item_id)
    return f"Marked {len(ids)} items as read."


def feeds_mark_all_read(feed_id: int | None = None) -> str:
    """Mark all items as read. Optionally scope to a single feed.
    feed_id: if provided, only mark items in this feed as read
    """
    count = mark_all_read(feed_id=feed_id)
    scope = f"in feed {feed_id}" if feed_id else "across all feeds"
    return f"Marked {count} items as read {scope}."


def feeds_add(url: str, tag: str = "") -> str:
    """Subscribe to a new RSS feed. Accepts website URL or direct feed URL.
    url: website or feed URL
    tag: optional tag to categorize the feed
    """
    tags = [tag] if tag else None
    feed = add_feed(url, tags=tags)
    return f"Subscribed to: {feed.title} ({feed.url})"


def feeds_delete(feed_id: int) -> str:
    """Unsubscribe from a feed and remove all its items.
    feed_id: the feed ID to delete
    """
    delete_feed(feed_id)
    return f"Deleted feed {feed_id} and all its items."


def feeds_list(tag: str = "") -> str:
    """List all subscribed feeds. Optionally filter by tag.
    tag: if provided, only show feeds with this tag
    """
    feeds = list_feeds(tag=tag or None)
    if not feeds:
        return "No feeds subscribed."
    lines = [f"[{f.id}] {f.title} — {f.url}" for f in feeds]
    return "\n".join(lines)


def feeds_refresh() -> str:
    """Fetch new items from all subscribed feeds."""
    results = update_all_feeds()
    total = sum(results.values())
    return f"Fetched {total} new items across {len(results)} feeds."


def feeds_get_items(
    feed_id: int | None = None, unread_only: bool = False, limit: int = 50
) -> str:
    """Get items with flexible filtering.
    feed_id: filter to a specific feed
    unread_only: if True, only return unread items
    limit: max number of items to return
    """
    items = get_items(feed_id=feed_id, unread_only=unread_only, limit=limit)
    if not items:
        return "No items found."
    lines = []
    for item in items:
        feed_title = item.feed.title if item.feed else "Unknown"
        status = "" if item.is_read else " [unread]"
        lines.append(f"[{item.id}] {feed_title} | {item.title}{status}")
        if item.url:
            lines.append(f"  {item.url}")
    return "\n".join(lines)
