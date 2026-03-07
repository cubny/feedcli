---
name: feedcli
description: >-
  RSS/Atom/JSON-Feed management tools for AI agents. Subscribe to feeds,
  fetch new articles, search content, manage read/star state, organize
  with categories and tags — backed by a local SQLite database with
  zero LLM token cost for data operations.
version: 0.3.0
tags: rss, feeds, news, content, reader
homepage: https://github.com/cubny/feedcli
source: https://github.com/cubny/feedcli
metadata:
  openclaw:
    requires:
      bins: ["python3", "pip"]
    install: "bash install.sh"
---

# feedcli Skill

RSS/Atom/JSON-Feed management tools backed by a local SQLite database. All data operations are deterministic with zero LLM token cost — intelligence (filtering, ranking, summarization) belongs in your agent logic, not in these tools.

## Primary Workflow: Digest Curation

1. **Fetch** — Call `feeds_refresh` to pull new items from all subscribed feeds.
2. **Read** — Call `feeds_get_unread` to get unread articles (titles, summaries, URLs, IDs).
3. **Evaluate** — Use your judgment to filter/rank articles by user interests.
4. **Mark processed** — Call `feeds_mark_read` with ALL processed item IDs (interesting or not) so they aren't re-processed next cycle.

**Important**: Always mark items as read after processing, even if they weren't interesting. Failing to do so causes items to accumulate and be re-evaluated every cycle.

## Available Tools

### Feeds

| Tool | Purpose | Key params |
|------|---------|------------|
| `feeds_add` | Subscribe to a new feed (auto-discovers from website URL) | `url`, `category` (optional) |
| `feeds_list` | List all subscribed feeds | `category` (optional filter) |
| `feeds_info` | Show details for a single feed | `feed_id` |
| `feeds_delete` | Remove a feed subscription | `feed_id` |
| `feeds_refresh` | Fetch new items from all feeds | — |
| `feeds_discover` | Discover feed URLs from a website without subscribing | `url` |
| `feeds_retry` | Reset error state and re-fetch a broken feed | `feed_id` |

### Items

| Tool | Purpose | Key params |
|------|---------|------------|
| `feeds_get_unread` | Get unread items for digest processing | `limit` (default 50) |
| `feeds_get_items` | Get items with flexible filtering | `feed_id`, `unread_only`, `limit` |
| `feeds_mark_read` | Mark items as read after processing | `item_ids` (comma-separated) |
| `feeds_mark_all_read` | Mark all items (or all in a feed) as read | `feed_id` (optional) |
| `items_mark_unread` | Mark an item as unread | `item_id` |
| `items_search` | Full-text search across item titles and content | `query`, `feed_id` (optional), `limit` |
| `items_star` | Star/bookmark an item | `item_id` |
| `items_unstar` | Remove star from an item | `item_id` |
| `items_starred` | List all starred items | `limit` |
| `items_get_url` | Get the URL for an item (for opening in browser) | `item_id` |

### Tags

| Tool | Purpose | Key params |
|------|---------|------------|
| `items_tag` | Add a user-defined tag to an item | `item_id`, `tag` |
| `items_by_tag` | List all items with a given tag | `tag`, `limit` (optional) |

### Categories

| Tool | Purpose | Key params |
|------|---------|------------|
| `categories_list` | List all categories in use | — |
| `categories_create` | Create a new category | `name` |
| `categories_set` | Assign a category to a feed | `feed_id`, `name` |

### OPML

| Tool | Purpose | Key params |
|------|---------|------------|
| `opml_import` | Import feeds from an OPML file | `file_path` |
| `opml_export` | Export all feeds to an OPML file | `file_path` |

### Database

| Tool | Purpose | Key params |
|------|---------|------------|
| `db_info` | Show database stats (feed/item counts, DB size) | — |

## Usage Patterns

### Adding feeds
```
# Auto-discovers feed URL from any website
feeds_add("https://blog.example.com")

# Direct feed URL with a category
feeds_add("https://example.com/feed.xml", category="tech")

# Discover feeds without subscribing
feeds_discover("https://example.com")
```

### Digest processing
```
# 1. Refresh all feeds
feeds_refresh()

# 2. Get unread items
feeds_get_unread(limit=30)

# 3. After evaluating, mark ALL items as read
feeds_mark_read("42,43,44,45,46")
```

### Searching and starring
```
# Full-text search
items_search("machine learning", limit=10)

# Star interesting items for later
items_star(42)

# Review starred items
items_starred()
```

### Categories
```
# Create a category
categories_create("tech")

# Move a feed to a category
categories_set(feed_id=1, name="tech")

# List feeds filtered by category
feeds_list(category="tech")
```

### OPML import/export
```
# Import feeds from another reader
opml_import("/path/to/subscriptions.opml")

# Export for backup
opml_export("/path/to/backup.opml")
```

### Item tagging
```
# Tag an item for future reference
items_tag(42, "urgent")
items_tag(42, "ai-research")

# Find items with a specific tag
items_by_tag("ai-research")
```

## Design Constraints

- **No LLM calls inside feedcli.** All intelligence (filtering, ranking, summarization) belongs in your agent logic, not in these tools. Tools only do CRUD and HTTP fetching.
- **Summaries are truncated to 300 chars** in `feeds_get_unread` output to keep token usage low. Full content is available via `feeds_get_items` if needed.
- **Item IDs are stable integers.** Use them for all mutation operations (mark read, star, tag).
- **Feed discovery is automatic.** Pass a website URL to `feeds_add` and it will find the RSS/Atom feed. Use direct feed URLs only if discovery fails.

## Security

See [SECURITY.md](SECURITY.md) for full access declarations. In summary:

- **Network**: Outbound HTTP(S) only — fetches user-provided feed URLs. No telemetry.
- **Filesystem**: Read/write only to `$XDG_DATA_HOME/feedcli/feedcli.db`. OPML import/export uses user-specified paths.
- **Credentials**: None required or stored.
- **Privileges**: No elevated access, no background processes, no shell injection.
- **Source code**: Fully open source at https://github.com/cubny/feedcli

## Setup

Automatic installation:

```bash
bash skills/feedcli/install.sh
```

Or manually:

```bash
pip install feedcli @ git+https://github.com/cubny/feedcli.git@v0.3.0
```

The database is stored at `$XDG_DATA_HOME/feedcli/feedcli.db` (default: `~/.local/share/feedcli/feedcli.db`). No setup required — tables are created automatically on first use.
