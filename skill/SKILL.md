# Feed Manager Skill

You have access to RSS/Atom/JSON-Feed management tools powered by feedcli. These tools let you subscribe to feeds, fetch new articles, and manage read state — all backed by a local SQLite database with zero LLM token cost for data operations.

## Primary Workflow: Digest Curation

The main use case is a periodic digest cycle:

1. **Fetch** — Call `feeds_refresh` to pull new items from all subscribed feeds.
2. **Read** — Call `feeds_get_unread` to get unread articles (titles, summaries, URLs, IDs).
3. **Evaluate** — Use your judgment to filter/rank articles by user interests.
4. **Mark processed** — Call `feeds_mark_read` with ALL processed item IDs (interesting or not) so they aren't re-processed next cycle.

**Important**: Always mark items as read after processing, even if they weren't interesting. Failing to do so causes items to accumulate and be re-evaluated every cycle.

## Available Tools

### Core tools (MVP)

| Tool | Purpose | Key params |
|------|---------|------------|
| `feeds_get_unread` | Get unread items for digest processing | `limit` (default 50) |
| `feeds_mark_read` | Mark items as read after processing | `item_ids` (comma-separated) |
| `feeds_add` | Subscribe to a new feed (auto-discovers from website URL) | `url`, `category` (optional) |
| `feeds_list` | List all subscribed feeds | `category` (optional filter) |
| `feeds_refresh` | Fetch new items from all feeds | — |
| `feeds_delete` | Remove a feed subscription | `feed_id` |
| `feeds_get_items` | Get items with flexible filtering | `feed_id`, `unread_only`, `limit` |
| `feeds_mark_all_read` | Mark all items (or all in a feed) as read | `feed_id` (optional) |
| `items_tag` | Add a user-defined tag to an item | `item_id`, `tag` |
| `items_by_tag` | List all items with a given tag | `tag`, `limit` (optional) |

### Extended tools (Phase 2+, when implemented)

| Tool | Purpose | Key params |
|------|---------|------------|
| `feeds_search` | Full-text search across items | `query`, `limit` |
| `feeds_star` | Bookmark an article | `item_id` |
| `feeds_starred` | List bookmarked articles | `limit` |

## Usage Patterns

### Adding feeds
```
# Auto-discovers feed URL from any website
feeds_add("https://blog.example.com")

# Direct feed URL with a category
feeds_add("https://example.com/feed.xml", category="tech")
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

### Listing feeds
```
# All feeds
feeds_list()

# Filtered by category
feeds_list(category="tech")
```

### Item tagging
```
# Tag an item for future reference or organization
items_tag(42, "urgent")
items_tag(42, "ai-research")

# Later, find items with a specific tag
items_by_tag("ai-research")
```

## Design Constraints

- **No LLM calls inside feedcli.** All intelligence (filtering, ranking, summarization) belongs in your agent logic, not in these tools. Tools only do CRUD and HTTP fetching.
- **Summaries are truncated to 300 chars** in `feeds_get_unread` output to keep token usage low. Full content is available via `feeds_get_items` if needed.
- **Item IDs are stable integers.** Use them for all mutation operations (mark read, star, delete).
- **Feed discovery is automatic.** Pass a website URL to `feeds_add` and it will find the RSS/Atom feed. Use direct feed URLs only if discovery fails.

## Setup

feedcli must be installed in the same Python environment as the agent:

```bash
pip install -e /path/to/feedcli
```

The database is stored at `$XDG_DATA_HOME/feedcli/feedcli.db` (default: `~/.local/share/feedcli/feedcli.db`). No setup required — tables are created automatically on first use.
