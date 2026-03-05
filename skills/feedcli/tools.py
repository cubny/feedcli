"""feedcli skill tools — callable by AI agents.

Each function returns a plain string suitable for LLM consumption.
feedcli must be pip install -e'd in the same Python environment.
"""

import json

from feedcli.ops import (
    add_feed,
    create_category,
    delete_feed,
    discover_feeds,
    export_opml,
    get_feed,
    get_item_url,
    get_items,
    get_items_by_tag,
    get_starred_items,
    get_unread_items,
    import_opml,
    list_categories,
    list_feeds,
    mark_all_read,
    mark_read,
    mark_unread,
    reset_feed_errors,
    search_items,
    set_feed_category,
    star_item,
    tag_item,
    unstar_item,
    update_all_feeds,
)
from feedcli.ops import (
    db_info as _db_info,
)

# ---------------------------------------------------------------------------
# Feeds
# ---------------------------------------------------------------------------


def feeds_add(url: str, category: str = "") -> str:
    """Subscribe to a new RSS feed. Accepts website URL or direct feed URL.
    url: website or feed URL
    category: optional category for the feed (defaults to 'default')
    """
    cat = category if category else None
    feed = add_feed(url, category=cat)
    return f"Subscribed to: {feed.title} ({feed.url})"


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


def feeds_info(feed_id: int) -> str:
    """Show details for a single feed.
    feed_id: the feed ID
    """
    f = get_feed(feed_id)
    lines = [
        f"ID: {f.id}",
        f"Title: {f.title}",
        f"URL: {f.url}",
        f"Website: {f.website or 'N/A'}",
        f"Category: {f.category.name if f.category else 'None'}",
        f"Created: {f.created_at}",
        f"Disabled: {f.disabled}",
        f"Error count: {f.error_count}",
    ]
    if f.last_error:
        lines.append(f"Last error: {f.last_error}")
    return "\n".join(lines)


def feeds_delete(feed_id: int) -> str:
    """Unsubscribe from a feed and remove all its items.
    feed_id: the feed ID to delete
    """
    delete_feed(feed_id)
    return f"Deleted feed {feed_id} and all its items."


def feeds_refresh() -> str:
    """Fetch new items from all subscribed feeds."""
    results = update_all_feeds()
    total = sum(results.values())
    return f"Fetched {total} new items across {len(results)} feeds."


def feeds_discover(url: str) -> str:
    """Discover feed URLs from a website without subscribing.
    url: website URL to discover feeds from
    """
    candidates = discover_feeds(url)
    if not candidates:
        return f"No feeds found at {url}"
    lines = []
    for c in candidates:
        lines.append(f"  {c.get('url', '?')} ({c.get('type', '?')}, {c.get('title', 'untitled')})")
    return f"Found {len(candidates)} feed(s):\n" + "\n".join(lines)


def feeds_retry(feed_id: int) -> str:
    """Reset error state and re-fetch a broken feed.
    feed_id: the feed ID to retry
    """
    count = reset_feed_errors(feed_id)
    return f"Reset errors for feed {feed_id}. Fetched {count} new item(s)."


# ---------------------------------------------------------------------------
# Items
# ---------------------------------------------------------------------------


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


def items_mark_unread(item_id: int) -> str:
    """Mark an item as unread.
    item_id: the ID of the item
    """
    mark_unread(item_id)
    return f"Marked item {item_id} as unread."


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


def items_search(query: str, feed_id: int | None = None, limit: int = 20) -> str:
    """Full-text search across item titles and content.
    query: search term
    feed_id: optional, restrict search to a specific feed
    limit: max number of results (default 20)
    """
    items = search_items(query, feed_id=feed_id, limit=limit)
    if not items:
        return f"No items matching '{query}'."
    lines = []
    for item in items:
        feed_title = item.feed.title if item.feed else "Unknown"
        status = "" if item.is_read else " [unread]"
        lines.append(f"[{item.id}] {feed_title} | {item.title}{status}")
        if item.url:
            lines.append(f"  {item.url}")
    return f"Found {len(items)} result(s):\n" + "\n".join(lines)


def items_star(item_id: int) -> str:
    """Star/bookmark an item.
    item_id: the ID of the item
    """
    star_item(item_id)
    return f"Starred item {item_id}."


def items_unstar(item_id: int) -> str:
    """Remove star from an item.
    item_id: the ID of the item
    """
    unstar_item(item_id)
    return f"Unstarred item {item_id}."


def items_starred(limit: int = 50) -> str:
    """List all starred items.
    limit: max number of items to return (default 50)
    """
    items = get_starred_items(limit=limit)
    if not items:
        return "No starred items."
    lines = []
    for item in items:
        feed_title = item.feed.title if item.feed else "Unknown"
        lines.append(f"[{item.id}] {feed_title} | {item.title} - {item.url}")
    return "\n".join(lines)


def items_get_url(item_id: int) -> str:
    """Get the URL for an item. Useful for opening in a browser.
    item_id: the ID of the item
    """
    url = get_item_url(item_id)
    return url


# ---------------------------------------------------------------------------
# Tags
# ---------------------------------------------------------------------------


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


# ---------------------------------------------------------------------------
# Categories
# ---------------------------------------------------------------------------


def categories_list() -> str:
    """List all categories in use."""
    cats = list_categories()
    if not cats:
        return "No categories."
    return "\n".join(cats)


def categories_create(name: str) -> str:
    """Create a new category.
    name: the category name
    """
    create_category(name)
    return f"Created category '{name}'."


def categories_set(feed_id: int, name: str) -> str:
    """Assign a category to a feed. Creates the category if it doesn't exist.
    feed_id: the feed ID
    name: the category name
    """
    set_feed_category(feed_id, name)
    return f"Set feed {feed_id} to category '{name}'."


# ---------------------------------------------------------------------------
# OPML
# ---------------------------------------------------------------------------


def opml_import(file_path: str) -> str:
    """Import feeds from an OPML file.
    file_path: path to the OPML file
    """
    feeds = import_opml(file_path)
    return f"Imported {len(feeds)} feed(s) from {file_path}."


def opml_export(file_path: str) -> str:
    """Export all feeds to an OPML file.
    file_path: destination path for the OPML file
    """
    export_opml(file_path)
    return f"Exported feeds to {file_path}."


# ---------------------------------------------------------------------------
# Database
# ---------------------------------------------------------------------------


def db_info() -> str:
    """Show database stats: feed count, item count, unread count, DB file size."""
    info = _db_info()
    size = info.get("db_size_bytes")
    size_str = f"{size:,} bytes" if size is not None else "N/A"
    return json.dumps(
        {
            "db_path": info["db_path"],
            "db_size": size_str,
            "feeds": info["feed_count"],
            "items": info["item_count"],
            "unread": info["unread_count"],
            "starred": info["starred_count"],
        },
        indent=2,
    )
