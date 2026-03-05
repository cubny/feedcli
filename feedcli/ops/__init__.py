"""High-level operations API — the primary interface for CLI and AI agent skills.

This package re-exports all public symbols from domain sub-modules for
backward compatibility. Existing imports like ``from feedcli.ops import add_feed``
continue to work unchanged.
"""

# Deprecated aliases — kept for backward compatibility
from feedcli.ops._deprecated import add_tag, get_feeds_by_tag, list_tags, remove_tag
from feedcli.ops.categories import (
    create_category,
    delete_category,
    get_feeds_by_category,
    list_categories,
    rename_category,
    reset_feed_category,
    set_feed_category,
)
from feedcli.ops.config import get_config, set_config
from feedcli.ops.database import db_backup, db_info, db_restore, db_vacuum
from feedcli.ops.feeds import (
    FeedAlreadyExistsError,
    add_feed,
    delete_feed,
    discover_feeds,
    get_feed,
    list_feeds,
    reset_feed_errors,
    update_all_feeds,
    update_feed,
)
from feedcli.ops.items import (
    delete_item,
    get_item,
    get_item_url,
    get_items,
    get_starred_items,
    get_unread_items,
    mark_all_read,
    mark_read,
    mark_unread,
    search_items,
    star_item,
    unstar_item,
)
from feedcli.ops.opml import export_opml, import_opml
from feedcli.ops.tags import (
    delete_tag,
    get_items_by_tag,
    list_item_tags,
    rename_tag,
    tag_item,
    untag_item,
)

__all__ = [
    # Feeds
    "FeedAlreadyExistsError",
    "add_feed",
    "list_feeds",
    "get_feed",
    "delete_feed",
    "update_feed",
    "update_all_feeds",
    "reset_feed_errors",
    "discover_feeds",
    # Items
    "get_unread_items",
    "get_items",
    "get_item",
    "mark_read",
    "mark_all_read",
    "mark_unread",
    "delete_item",
    "search_items",
    "star_item",
    "unstar_item",
    "get_starred_items",
    "get_item_url",
    # Categories
    "list_categories",
    "create_category",
    "delete_category",
    "rename_category",
    "set_feed_category",
    "reset_feed_category",
    "get_feeds_by_category",
    # Item Tags
    "tag_item",
    "untag_item",
    "list_item_tags",
    "get_items_by_tag",
    "delete_tag",
    "rename_tag",
    # OPML
    "import_opml",
    "export_opml",
    # Config
    "get_config",
    "set_config",
    # Database
    "db_info",
    "db_vacuum",
    "db_backup",
    "db_restore",
    # Deprecated aliases
    "list_tags",
    "add_tag",
    "remove_tag",
    "get_feeds_by_tag",
]
