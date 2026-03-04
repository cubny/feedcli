# feedcli — Specification

Last updated: 2026-02-23

## Overview

feedcli is a local Python library + CLI for RSS/Atom/JSON-Feed management. It provides programmatic CRUD operations on feeds and items backed by a local SQLite database.

**Primary consumer**: Nova (AI agent) imports `feedcli.ops` as a Python library via a Nova skill plugin. Nova uses feedcli as a data source for proactive content curation — periodically pulling unread items, using its LLM to filter by user interests, and sending relevant articles via Telegram.

**Design constraint**: feedcli uses zero LLM tokens. All operations are deterministic CRUD and HTTP fetching. Intelligence (filtering, ranking, summarization) belongs in the consumer (Nova), not in feedcli.

---

## The Digest Workflow

This is the primary use case feedcli is designed for:

```
                    ┌─────────────┐
                    │   feedcli   │
                    │  (library)  │
                    └──────┬──────┘
                           │
        ┌──────────────────┼──────────────────┐
        │                  │                  │
   1. Auto-fetch      2. get_unread()    4. mark_read()
   (cron/daemon)           │                  │
   fetches feeds      ┌────┴────┐        ┌────┴────┐
   stores items       │  Nova   │        │  Nova   │
   no LLM needed      │  skill  │        │  skill  │
                       └────┬────┘        └─────────┘
                            │
                    3. LLM filters by
                       user interests
                            │
                    Telegram message
                    (interesting articles only)
```

**Step 1**: feedcli's daemon or a system cron job runs `feedcli feeds update --all` periodically (e.g. every hour). This fetches new items from all subscribed feeds and stores them in SQLite. No LLM involved.

**Step 2**: Nova's cron job calls `feedcli.ops.get_unread_items(limit=N)` to pull unread items (titles, summaries, URLs, feed names).

**Step 3**: Nova passes the item list to its LLM, which filters/ranks based on user interests stored in Nova's semantic memory (Mem0). This is where LLM tokens are spent — only on the compact title+summary text, not on raw feed XML.

**Step 4**: Nova calls `feedcli.ops.mark_read(item_ids)` for all processed items (whether interesting or not), so they aren't re-processed next cycle.

---

## Design Goals

- **Library-first**: `feedcli.ops` is the primary API. The CLI is a thin wrapper. External consumers import the library directly — no HTTP, no serialization, no process management.
- **Scriptable**: All list/show commands support `--format json|table` and `--quiet` for automation. JSON is the default format.
- **ID-first operations**: Stable integer IDs for all feeds and items. All mutation operations take IDs.
- **Local SQLite store**: File-based DB respecting XDG dirs — default `$XDG_DATA_HOME/feedcli/feedcli.db` (falls back to `~/.local/share/feedcli/feedcli.db`). No server, no auth.
- **Single-user, single-process**: No multi-tenancy. feedcli and Nova share the same Python process when used as a library.
- **Conditional fetching**: Use ETag/Last-Modified to minimize bandwidth on repeated fetches.

---

## Technology Stack

- Python 3.10+ (3.12 recommended to match Nova)
- **feedparser** — RSS/Atom/JSON-Feed parsing
- **click** — CLI framework
- **SQLAlchemy** (ORM) + **Alembic** (migrations, optional but recommended for schema evolution)
- **httpx** — HTTP client (async-capable, matches Nova's stack)
- **beautifulsoup4** — HTML parsing for feed discovery
- **python-dateutil** — date normalization
- **pytest** — testing

Dev & packaging:
- **hatch** or **poetry** — dependency management and packaging
- **ruff** — linting and formatting
- **pre-commit** — git hooks for linting

---

## Project Layout

```
feedcli/
├── feedcli/
│   ├── __init__.py
│   ├── cli.py                 # Click CLI (thin wrapper around ops.py)
│   ├── config.py              # XDG config loading/saving
│   ├── db.py                  # SQLAlchemy engine, session factory
│   ├── models.py              # ORM models (Feed, Item, Tag)
│   ├── discovery.py           # Feed URL discovery from websites
│   ├── fetcher.py             # Feed fetching, parsing, conditional GET
│   ├── ops.py                 # High-level operations API (primary interface)
│   ├── opml.py                # OPML import/export
│   ├── utils.py               # Helpers (date parsing, URL normalization)
│   └── daemon.py              # Background fetch scheduler (optional)
├── tests/
│   ├── test_discovery.py
│   ├── test_fetcher.py
│   ├── test_ops.py
│   └── test_cli.py
├── pyproject.toml
├── CLAUDE.md
├── AGENTS.md
└── docs/
    └── spec.md                # This file
```

---

## Primary API: `ops.py`

This is the interface Nova's skill imports. All functions accept an optional `session` parameter (SQLAlchemy session); if omitted, they create one internally.

### Feed operations

```python
def add_feed(url: str, title: str | None = None, tags: list[str] | None = None,
             auto_discover: bool = True) -> Feed
    """Subscribe to a feed. Auto-discovers feed URL from website URL by default.
    Optionally assign tags at subscription time. Returns the Feed ORM object."""

def list_feeds(tag: str | None = None) -> list[Feed]
    """List all subscribed feeds with unread counts. Optionally filter by tag."""

def get_feed(feed_id: int) -> Feed
    """Get a single feed by ID."""

def delete_feed(feed_id: int) -> None
    """Delete a feed and all its items."""

def update_feed(feed_id: int) -> int
    """Fetch new items for a single feed. Returns count of new items."""

def update_all_feeds(jobs: int = 4) -> dict[int, int]
    """Fetch new items for all feeds (parallel). Returns {feed_id: new_item_count}."""

def discover_feeds(url: str, timeout: int = 30) -> list[dict]
    """Discover feed URLs from a website URL without subscribing.
    Returns list of {url, type, version, title, items_count}."""
```

### Item operations

```python
def get_unread_items(feed_id: int | None = None, limit: int = 50) -> list[Item]
    """Get unread items, optionally filtered by feed. Ordered by published_at desc.
    This is the primary function Nova's digest cron job calls."""

def get_items(feed_id: int | None = None, unread_only: bool = False,
              starred_only: bool = False, limit: int = 50, offset: int = 0) -> list[Item]
    """Get items with flexible filtering."""

def get_item(item_id: int) -> Item
    """Get a single item by ID."""

def get_item_url(item_id: int) -> str
    """Get just the URL for an item. Useful for opening in browser."""

def mark_read(item_id: int) -> None
    """Mark a single item as read."""

def mark_unread(item_id: int) -> None
    """Mark a single item as unread."""

def mark_all_read(feed_id: int | None = None) -> int
    """Mark all items (or all items in a feed) as read. Returns count affected."""

def delete_item(item_id: int, hard: bool = False) -> None
    """Delete an item. Soft-delete by default (sets deleted=True), hard-delete removes from DB."""

def search_items(query: str, feed_id: int | None = None, limit: int = 20) -> list[Item]
    """Full-text search across item titles and content."""

def star_item(item_id: int) -> None
    """Star/bookmark an item."""

def unstar_item(item_id: int) -> None
    """Remove star from an item."""

def get_starred_items(limit: int = 50) -> list[Item]
    """Get all starred items."""
```

### Tag operations

```python
def list_tags() -> list[str]
    """List all tags in use."""

def add_tag(feed_id: int, tag: str) -> None
    """Add a tag to a feed."""

def remove_tag(feed_id: int, tag: str) -> None
    """Remove a tag from a feed."""

def get_feeds_by_tag(tag: str) -> list[Feed]
    """Get all feeds with a given tag."""
```

### OPML operations

```python
def import_opml(file_path: str) -> list[Feed]
    """Import feeds from an OPML file. Returns list of added feeds."""

def export_opml(file_path: str) -> None
    """Export all feeds to an OPML file."""
```

### Config operations

```python
def get_config() -> dict
    """Get current configuration as a dictionary."""

def set_config(key: str, value: str) -> None
    """Set a configuration value."""
```

### Database operations

```python
def db_info() -> dict
    """Get database stats: feed count, item count, DB file size, etc."""

def db_vacuum() -> None
    """Compact the SQLite database."""

def db_backup(dest_path: str) -> None
    """Backup the database to a file."""

def db_restore(src_path: str) -> None
    """Restore the database from a backup file."""
```

---

## Database Schema

SQLite database at `$XDG_DATA_HOME/feedcli/feedcli.db` (default: `~/.local/share/feedcli/feedcli.db`).

```python
class Feed(Base):
    __tablename__ = "feeds"
    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)    # Feed URL (RSS/Atom/JSON)
    title = Column(String)
    website = Column(String)                              # Source website URL
    etag = Column(String, nullable=True)                  # HTTP ETag for conditional GET
    last_modified = Column(String, nullable=True)         # HTTP Last-Modified
    last_fetched_at = Column(DateTime, nullable=True)     # When we last fetched
    last_error = Column(String, nullable=True)            # Last fetch error message
    error_count = Column(Integer, default=0)              # Consecutive error count
    disabled = Column(Boolean, default=False)             # Disabled after too many errors
    created_at = Column(DateTime)

    items = relationship("Item", back_populates="feed", cascade="all, delete-orphan")
    tags = relationship("Tag", back_populates="feed", cascade="all, delete-orphan")

class Item(Base):
    __tablename__ = "items"
    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("feeds.id"), index=True)
    guid = Column(String, index=True)                     # Feed-provided unique ID
    title = Column(String)
    url = Column(String)                                  # Article URL
    author = Column(String)
    summary = Column(Text)                                # Short summary/description
    content = Column(Text)                                # Full content (if available)
    published_at = Column(DateTime, index=True)
    fetched_at = Column(DateTime)
    is_read = Column(Boolean, default=False, index=True)
    is_starred = Column(Boolean, default=False, index=True)
    deleted = Column(Boolean, default=False)               # Soft-delete flag

    feed = relationship("Feed", back_populates="items")

class Tag(Base):
    __tablename__ = "tags"
    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("feeds.id"), index=True)
    name = Column(String, nullable=False)

    feed = relationship("Feed", back_populates="tags")

    __table_args__ = (UniqueConstraint("feed_id", "name", name="uq_tag_feed_name"),)

# Indexes
Index("ix_items_feed_unread", Item.feed_id, Item.is_read)
UniqueConstraint("feed_id", "guid", name="uq_item_feed_guid")
Index("ix_tags_name", Tag.name)
```

Key decisions:
- `guid` + `feed_id` is unique — prevents duplicate items.
- `summary` and `content` are separate — Nova's digest only needs `summary` to minimize LLM token usage. `content` is stored for when the user wants to read the full article.
- `etag`/`last_modified` on Feed enable conditional HTTP requests.
- `last_error`/`error_count`/`disabled` enable automatic backoff for broken feeds.
- `deleted` on Item enables soft-delete (items can be hidden without removing from DB).
- Tags are a separate model linked to Feed — allows multi-tag per feed and tag-based filtering.

---

## Feed Discovery Algorithm

Given a URL (website or feed), return candidate feed URLs.

1. **Direct probe**: GET the URL. If `Content-Type` is XML/feed-like or feedparser parses it successfully (`.version` present), accept as feed.
2. **HTML link tags**: Parse the HTML for `<link>` with types:
   - `application/rss+xml`
   - `application/atom+xml`
   - `application/feed+json`
   - `application/xml`, `text/xml` (fallback)
   - Resolve relative `href` via `urljoin`.
3. **Well-known paths**: Try `/feed.json`, `/.well-known/feed+json`.
4. **Common endpoints**: Try `/feed`, `/rss`, `/rss.xml`, `/atom.xml`, `/?feed=rss2` (WordPress), `/feeds/posts/default` (Blogger).
5. **Validate**: For each candidate, probe with feedparser to confirm valid feed.
6. **Deduplicate** and return list of `{url, type, version, title, items_count}`.

When called via `add_feed()` with `auto_discover=True`:
- If one candidate found, use it automatically.
- If multiple candidates found, use the first one (prefer RSS over Atom over JSON-Feed).
- Via CLI with multiple candidates, list them and let the user pick with `--auto` to accept first.
- `--no-discover` skips discovery entirely and treats the URL as a direct feed URL.
- `--timeout` controls discovery HTTP timeout (default: 30s).

---

## Fetcher Design

Responsibilities:
- Given a Feed record, perform HTTP conditional GET using `If-None-Match`/`If-Modified-Since` when `etag`/`last_modified` are present.
- Parse response via feedparser.
- For each entry, create/update Item using `(feed_id, guid)` for deduplication. Fallback to `(feed_id, url)` if no GUID.
- Update feed-level `etag`, `last_modified`, `last_fetched_at`.
- Record errors in `last_error`, increment `error_count`. Disable feed after configurable threshold (default: 10 consecutive errors).

Implementation:
- Use httpx for HTTP (sync initially, async migration path available).
- `update_all_feeds()` uses `concurrent.futures.ThreadPoolExecutor` for parallel fetching. Pool size configurable via `--jobs N` (default: 4).
- Respect configurable timeout (default: 30s per feed).
- Respect site politeness: configurable per-host rate limits to avoid hammering servers.

---

## CLI Commands

JSON is the default output format. All list/show commands support `--format json|table` and `--quiet` (suppress non-data output). Global flags: `--timeout`, `--quiet`.

### Feeds

```
feedcli feeds list [--tag TAG] [--format json|table] [--quiet]
feedcli feeds add <url> [--title T] [--tag TAG] [--no-discover] [--auto] [--quiet]
feedcli feeds info <feed-id> [--format json|table]
feedcli feeds delete <feed-id> [--force]
feedcli feeds update [<feed-id>] [--all] [--jobs N] [--timeout N]
feedcli feeds discover <url> [--format json|urls] [--timeout N]
feedcli feeds retry <feed-id>
```

### Items

```
feedcli items list [--feed <feed-id>] [--unread] [--starred] [--limit N] [--format json|table|ids] [--quiet]
feedcli items show <item-id> [--format json|table]
feedcli items get-url <item-id> [--quiet]
feedcli items mark-read <item-id>
feedcli items mark-read --feed <feed-id>
feedcli items mark-read --all
feedcli items mark-unread <item-id>
feedcli items delete <item-id> [--hard]
feedcli items search <query> [--feed <feed-id>] [--limit N] [--format json|table]
feedcli items star <item-id>
feedcli items unstar <item-id>
feedcli items starred [--limit N] [--format json|table]
```

### Tags

```
feedcli tags list [--format json|table]
feedcli tags add <feed-id> <tag>
feedcli tags remove <feed-id> <tag>
feedcli tags show <tag> [--format json|table]
```

### OPML

```
feedcli opml import <file>
feedcli opml export <file>
```

### Config

```
feedcli config show
feedcli config set <key> <value>
```

### Database

```
feedcli db info
feedcli db vacuum
feedcli db path
feedcli db backup <dest-path>
feedcli db restore <src-path> [--force]
```

### Daemon

```
feedcli daemon start [--interval MINUTES]
feedcli daemon stop
feedcli daemon status
feedcli daemon logs [--lines N]
```

The daemon runs `update_all_feeds()` on a configurable interval (default: 60 minutes). Alternative: use system cron (`crontab -e`) or Nova's built-in scheduler to call `feedcli feeds update --all`.

---

## Error Handling

- Per-feed error tracking: `last_error`, `error_count` fields.
- Exponential backoff: feeds with `error_count > 0` are skipped if last fetch was within `2^error_count` minutes (capped at 24 hours).
- Auto-disable: feeds with `error_count >= 10` are set to `disabled=True` and skipped.
- `feeds retry <feed-id>`: resets `error_count` and `disabled`, forces immediate fetch.
- All network operations use configurable timeouts. Fetch failures are logged but never crash the process.
- Confirm destructive operations by default; `--force` to bypass confirmation.

---

## Storage & Deduplication

- Deduplicate items by `(feed_id, guid)`. Fallback: `(feed_id, url)`.
- Store both `summary` (short description) and `content` (full article when available).
- Soft-delete items by default (`deleted=True`); `--hard` flag for permanent removal.
- `db vacuum` command to compact SQLite.
- `db path` command to show database file location.
- `db backup`/`db restore` for database backup and recovery.

---

## Nova Skill Integration

feedcli is consumed by Nova as a **skill plugin** at `~/.nova/skills/feeds/`:

```
~/.nova/skills/feeds/
├── skill.yaml
├── tools.py
└── SKILL.md
```

**skill.yaml**:
```yaml
name: "Feed Manager"
instruction: |
  You have access to RSS feed management tools. Use feeds_get_unread to pull
  new articles for digest processing. After evaluating articles, always call
  feeds_mark_read for all processed item IDs (whether interesting or not).
```

**tools.py** — imports `feedcli.ops` directly:
```python
from feedcli.ops import (
    add_feed, list_feeds, get_unread_items, mark_read,
    mark_all_read, update_all_feeds, search_items, star_item,
    get_starred_items, list_tags, get_feeds_by_tag
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
        lines.append(f"[{item.id}] {item.feed.title} | {item.title}")
        if item.summary:
            lines.append(f"  {item.summary[:300]}")
        lines.append(f"  {item.url}")
        lines.append("")
    return "\n".join(lines)

def feeds_mark_read(item_ids: str) -> str:
    """Mark items as read after digest processing.
    item_ids: comma-separated item IDs
    """
    ids = [int(x.strip()) for x in item_ids.split(",") if x.strip()]
    for id in ids:
        mark_read(id)
    return f"Marked {len(ids)} items as read."

def feeds_add(url: str, tag: str = "") -> str:
    """Subscribe to a new RSS feed. Accepts website URL or direct feed URL.
    tag: optional tag to categorize the feed
    """
    tags = [tag] if tag else None
    feed = add_feed(url, tags=tags)
    return f"Subscribed to: {feed.title} ({feed.url})"

def feeds_list(tag: str = "") -> str:
    """List all subscribed feeds with unread counts. Optionally filter by tag."""
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

def feeds_search(query: str, limit: int = 10) -> str:
    """Search across all feed items by keyword."""
    items = search_items(query, limit=limit)
    if not items:
        return "No results."
    lines = [f"[{i.id}] {i.feed.title} | {i.title}\n  {i.url}" for i in items]
    return "\n".join(lines)

def feeds_star(item_id: int) -> str:
    """Star/bookmark an interesting article for later reference."""
    star_item(item_id)
    return f"Starred item {item_id}."

def feeds_starred(limit: int = 20) -> str:
    """List all starred/bookmarked articles."""
    items = get_starred_items(limit=limit)
    if not items:
        return "No starred items."
    lines = [f"[{i.id}] {i.feed.title} | {i.title}\n  {i.url}" for i in items]
    return "\n".join(lines)
```

feedcli must be `pip install -e`'d in the same Python environment where Nova runs, so the imports resolve.

---

## Configuration

Config file at `$XDG_CONFIG_HOME/feedcli/config.toml` (default: `~/.config/feedcli/config.toml`):

```toml
[database]
path = "~/.local/share/feedcli/feedcli.db"

[fetch]
timeout = 30          # seconds per feed
jobs = 4              # parallel fetch threads
max_errors = 10       # consecutive errors before disabling feed

[daemon]
interval = 60         # minutes between auto-fetches
```

Environment variables override config: `FEEDCLI_DB_PATH`, `FEEDCLI_FETCH_TIMEOUT`, `FEEDCLI_FETCH_JOBS`.

CLI management:
- `feedcli config show` — display current config.
- `feedcli config set <key> <value>` — update a config value.

---

## Testing Strategy

- **Unit tests for discovery**: Recorded HTML samples with various `<link>` configurations.
- **Unit tests for fetcher**: Static feed XML/Atom/JSON fixtures parsed offline.
- **Unit tests for ops**: Temporary SQLite DB, test full CRUD lifecycle.
- **CLI tests**: Click's `CliRunner` for command invocation and JSON output validation.
- **Integration tests**: `pytest-httpserver` for end-to-end fetch→store→query cycles.

All tests use temporary databases (`:memory:` or `tmp_path`) — never touch the real DB.

---

## CI / Lint / Packaging

- **GitHub Actions**: Tests on push/PR (matrix: Python 3.10, 3.11, 3.12). Build wheel, run linters.
- **pre-commit**: ruff for linting and formatting.
- **Packaging**: `pyproject.toml` with console script entrypoint:
  ```toml
  [project.scripts]
  feedcli = "feedcli.cli:main"
  ```
- **Installation**: `pip install -e .` for development, `pipx install feedcli` for end users.
- **PyPI**: Tag-based release publishing via GitHub Actions (optional).

---

## Milestones

**MVP** — Core feed management + Nova skill integration
- SQLAlchemy models + DB initialization (Feed, Item, Tag)
- `ops.py`: `add_feed`, `list_feeds`, `delete_feed`, `get_unread_items`, `mark_read`, `mark_all_read`
- Basic fetcher (single-threaded, feedparser)
- Basic discovery (HTML link tags + direct probe)
- CLI: `feeds add/list/delete/update`, `items list/show/mark-read`
- Nova skill: `tools.py` + `skill.yaml`
- Tests for ops + fetcher

**Phase 2** — Robustness + search + tags
- Parallel fetching with thread pool
- Conditional GET (ETag/Last-Modified)
- Error tracking + exponential backoff
- `search_items` (SQLite FTS or LIKE)
- Star/bookmark support
- Tag CRUD (`tags list/add/remove/show`, `--tag` filter on feeds)
- Item soft-delete + `items delete` command
- OPML import/export

**Phase 3** — Daemon + polish + ops
- Background daemon with configurable interval + `daemon logs`
- `db info/vacuum/path/backup/restore` commands
- `config show/set` commands
- `items get-url` command
- `feeds discover` command (standalone discovery without subscribing)
- Feed retry command
- `--quiet` global flag, `--format ids` on items list, `--format urls` on discover
- Per-host rate limiting / politeness

**Phase 4** — Future (optional)
- Async rewrite (httpx async + asyncio)
- Alembic migrations for schema evolution
- Plugin/hooks system for extensibility

---

## Security & Privacy

- All data stored locally. No telemetry, no external API calls except fetching subscribed feeds.
- Respect XDG dirs: config in `$XDG_CONFIG_HOME/feedcli`, data/db in `$XDG_DATA_HOME/feedcli`.
- Configurable HTTP timeout, proxy, and TLS verification settings for feed fetching.
- No remote code execution. HTML content from feeds is stored as-is but never rendered/executed.
