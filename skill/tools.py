"""feedcli skill tools — callable by AI agents.

Each function returns a plain string suitable for LLM consumption.
feedcli must be pip install -e'd in the same Python environment.
"""

from feedcli.ops import (
    add_feed,
    delete_feed,
    get_items,
    get_items_by_tag,
    get_unread_items,
    list_feeds,
    mark_all_read,
    mark_read,
    tag_item,
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
        if item.tags:
            tags = ", ".join(t.name for t in item.tags)
            lines.append(f"  Tags: {tags}")
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


def feeds_add(url: str, category: str = "") -> str:
    """Subscribe to a new RSS feed. Accepts website URL or direct feed URL.
    url: website or feed URL
    category: optional category for the feed (defaults to 'default')
    """
    cat = category if category else None
    feed = add_feed(url, category=cat)
    return f"Subscribed to: {feed.title} ({feed.url})"


def feeds_delete(feed_id: int) -> str:
    """Unsubscribe from a feed and remove all its items.
    feed_id: the feed ID to delete
    """
    delete_feed(feed_id)
    return f"Deleted feed {feed_id} and all its items."


def feeds_list(category: str = "") -> str:
    """List all subscribed feeds. Optionally filter by category.
    category: if provided, only show feeds in this category
    """
    feeds = list_feeds(category=category or None)
    if not feeds:
        return "No feeds subscribed."
    lines = [
        f"[{f.id}] {f.title} — {f.url} (Category: {f.category.name if f.category else 'None'})"
        for f in feeds
    ]
    return "\n".join(lines)


def feeds_refresh() -> str:
    """Fetch new items from all subscribed feeds."""
    results = update_all_feeds()
    total = sum(results.values())
    return f"Fetched {total} new items across {len(results)} feeds."


def feeds_get_items(feed_id: int | None = None, unread_only: bool = False, limit: int = 50) -> str:
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
        if item.tags:
            tags = ", ".join(t.name for t in item.tags)
            lines.append(f"  Tags: {tags}")
    return "\n".join(lines)


def items_tag(item_id: int, tag: str) -> str:
    """Add a tag to a specific item.
    item_id: the ID of the item
    tag: the tag to add
    """
    tag_item(item_id, tag)
    return f"Added tag '{tag}' to item {item_id}."


def items_by_tag(tag: str, limit: int = 50) -> str:
    """Get items that have a specific tag.
    tag: the tag to filter by
    limit: max number of items to return
    """
    items = get_items_by_tag(tag, limit=limit)
    if not items:
        return f"No items with tag '{tag}' found."
    lines = []
    for item in items:
        feed_title = item.feed.title if item.feed else "Unknown"
        status = "" if item.is_read else " [unread]"
        lines.append(f"[{item.id}] {feed_title} | {item.title}{status} - {item.url}")
    return "\n".join(lines)
