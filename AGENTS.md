# AGENTS.md

Guidelines for any AI coding agent working on this repository.

## Maintenance Policy

**This file must be kept up to date.** After every change to the codebase:
1. Update this file and `CLAUDE.md` with any new files, changed APIs, new commands, or architectural decisions.
2. Add lessons learned under the "Lessons Learned" section to avoid repeating mistakes.
3. If `feedcli/ops/` function signatures change, note the breaking change and what downstream consumers (AI agent skills) need to update.

## Project Summary

feedcli is a local Python RSS/Atom/JSON-Feed management library with a CLI interface. It is designed as a **data source for AI agents** that need to consume RSS feeds without spending LLM tokens on fetching, parsing, or storing feed data.

**Primary use case**: An AI agent runs a periodic cron job that:
1. Calls `feedcli.ops.get_unread_items()` to pull new articles
2. Uses its LLM to filter/rank articles by user interests
3. Sends relevant articles to the user (e.g. via Telegram, email, etc.)
4. Calls `feedcli.ops.mark_read()` for all processed items

feedcli handles steps 1 and 4. Steps 2 and 3 happen in the consuming agent. feedcli itself never calls any LLM.

## Architecture Principles

1. **Library-first**: `feedcli/ops/` is the primary API (a package with `__init__.py` re-exporting all public symbols). The CLI (`feedcli/cli.py`) is a thin wrapper. External consumers (AI agent skills) import `feedcli.ops` directly as a Python library.
2. **No network services**: feedcli is not a server. It is a library + CLI that reads/writes a local SQLite database. No HTTP API, no auth, no ports.
3. **Deterministic**: All operations are pure CRUD + HTTP feed fetching. No randomness, no LLM calls, no external APIs beyond fetching feeds.
4. **Minimal dependencies**: feedparser, click, SQLAlchemy, httpx, beautifulsoup4, python-dateutil. No heavy frameworks.

## Key Files

| File | Purpose |
|------|---------|
| `feedcli/ops/__init__.py` | **Primary API** — re-exports all public symbols for backward compat (`from feedcli.ops import add_feed` still works) |
| `feedcli/ops/_session.py` | `managed_session()` context manager — replaces old `_get_session` + try/finally/rollback boilerplate |
| `feedcli/ops/feeds.py` | Feed CRUD, update, discovery. Contains `FeedAlreadyExistsError`. |
| `feedcli/ops/items.py` | Item read/write/search/star operations |
| `feedcli/ops/categories.py` | Category CRUD operations |
| `feedcli/ops/tags.py` | Item tag CRUD operations |
| `feedcli/ops/opml.py` | OPML import/export (wraps `feedcli.opml`) |
| `feedcli/ops/config.py` | Config get/set (wraps `feedcli.config`) |
| `feedcli/ops/database.py` | DB info/vacuum/backup/restore |
| `feedcli/ops/_deprecated.py` | Deprecated aliases (`list_tags`, `add_tag`, `remove_tag`, `get_feeds_by_tag`) |
| `feedcli/models.py` | SQLAlchemy ORM models: `Feed`, `Item`, `Category`, `ItemTag` with indexes and constraints |
| `feedcli/db.py` | Database engine + session factory (`get_engine`, `get_session`, `reset_engine`) |
| `feedcli/discovery.py` | Feed URL discovery from websites (probe → HTML links → well-known → common paths) |
| `feedcli/fetcher.py` | Feed fetching with httpx + feedparser, conditional GET, dedup, error tracking |
| `feedcli/cli.py` | Click CLI — `feeds` and `items` command groups, JSON default output |
| `feedcli/config.py` | XDG-compliant config loading with env var overrides |
| `feedcli/utils.py` | Date parsing (`parse_date`) and URL normalization (`normalize_url`) |
| `docs/spec.md` | Full implementation specification — **source of truth for design** |
| `skills/feedcli/SKILL.md` | Agent-facing skill documentation — how AI agents use feedcli |
| `skills/feedcli/tools.py` | Callable tool functions wrapping `feedcli.ops`, returning plain strings |
| `tests/conftest.py` | Shared pytest fixtures: in-memory DB session, sample feed/HTML fixtures |

## ops/ API Surface (MVP)

These are the functions AI agent skills import. **Signature changes are breaking.**
The `feedcli/ops/` package re-exports all public symbols via `__init__.py`, so
`from feedcli.ops import add_feed` continues to work.

```python
add_feed(url, title=None, tags=None, auto_discover=True, session=None) -> Feed
list_feeds(tag=None, session=None) -> list[Feed]
get_feed(feed_id, session=None) -> Feed
delete_feed(feed_id, session=None) -> None
update_feed(feed_id, timeout=30, session=None) -> int
update_all_feeds(jobs=4, timeout=30, session=None) -> dict[int, int]
get_unread_items(feed_id=None, limit=50, session=None) -> list[Item]
get_items(feed_id=None, unread_only=False, limit=50, offset=0, session=None) -> list[Item]
get_item(item_id, session=None) -> Item
mark_read(item_id, session=None) -> None
mark_all_read(feed_id=None, session=None) -> int
```

## Development Guidelines

- **Read `docs/spec.md`** before implementing any feature. It is the source of truth for schema, CLI commands, discovery algorithm, and fetcher design.
- **Test with pytest**. Use `:memory:` SQLite databases for isolation. Test fixtures live in `tests/fixtures/`.
- **Mock HTTP with respx** (for httpx). Use `@respx.mock` decorator + `respx.get().mock()`. Never make real network calls in tests.
- **Lint with ruff**. Run `ruff check .` before considering work done. Fix all errors.
- **Don't add LLM dependencies**. feedcli must remain model-free. Intelligence belongs in the consuming agent, not here.
- **Protect the `feedcli.ops` API surface**. AI agent skills import these functions directly. Signature changes require updating `skills/feedcli/tools.py` and any downstream consumers.
- **Mock patch paths**: When mocking ops internals in tests, patch at the domain module level (e.g., `feedcli.ops.feeds._discover_feeds`, `feedcli.ops.feeds.fetch_feed`), not at `feedcli.ops`.
- **JSON is the default output format** for CLI commands. Human-readable table format is secondary.
- **Update CLAUDE.md and AGENTS.md** after every significant change — new files, API changes, architecture decisions, lessons learned.

## How AI Agents Consume feedcli

AI agents use a **skill plugin** (`skills/feedcli/tools.py`) that imports from `feedcli.ops`:

```python
# skills/feedcli/tools.py
from feedcli.ops import get_unread_items, mark_read, add_feed, list_feeds

def feeds_get_unread(limit: int = 50) -> str:
    """Get unread feed items. Returns titles, summaries, and IDs."""
    items = get_unread_items(limit=limit)
    # Format for LLM consumption
    ...

def feeds_mark_read(item_ids: str) -> str:
    """Mark items as read after processing. item_ids: comma-separated IDs."""
    for id in item_ids.split(","):
        mark_read(int(id.strip()))
    return "Done."
```

This is a direct Python import — no HTTP, no serialization, no process management. feedcli and the consuming agent share the same Python process.

## Testing

```bash
pytest                          # All tests (112 tests)
pytest tests/test_discovery.py  # Discovery logic (5 tests)
pytest tests/test_fetcher.py    # Feed parsing (9 tests)
pytest tests/test_cli.py        # CLI commands (11 tests)
pytest tests/test_ops.py        # Operations API (83 tests)
ruff check .                    # Lint (must pass with 0 errors)
```

## Current Status

**MVP complete.** Not yet implemented (Phase 2+): parallel fetching, search, star/bookmark, tags CLI, OPML, daemon, soft-delete CLI, config CLI, db management CLI.

## Lessons Learned

- **ruff import sorting (I001)**: ruff enforces sorted import blocks. Don't separate third-party imports with blank lines. Use `ruff check . --fix` to auto-fix.
- **Line length 100**: Configured in `pyproject.toml`. Break long docstrings and test lines accordingly.
- **`datetime.utcnow()` deprecation**: Python 3.12+ warns about this. Used throughout MVP; future cleanup should migrate to `datetime.now(datetime.UTC)`.
- **respx, not responses**: Use `respx` to mock httpx calls (not `responses` which is for the `requests` library). Decorator: `@respx.mock`.
- **SQLAlchemy boolean filters**: Must use `== False` / `== True` (not `is`). Add `# noqa: E712` to suppress ruff warning — SQLAlchemy needs `==` for SQL generation.
- **Click CliRunner testing**: Patch `feedcli.cli.get_session` to inject in-memory DB sessions. The CLI creates its session in `main()`'s `@click.pass_context`.
- **feedparser content field**: feedparser returns `entry["content"]` as a list of dicts with a `"value"` key, not a plain string. Access via `entry["content"][0]["value"]`.
- **ops/ package refactor**: `feedcli/ops.py` was split into `feedcli/ops/` package with domain modules (`feeds.py`, `items.py`, `categories.py`, `tags.py`, `opml.py`, `config.py`, `database.py`). The `__init__.py` re-exports everything for backward compat. Mock patches must target the domain module (e.g., `feedcli.ops.feeds._discover_feeds`), not `feedcli.ops`.
- **`managed_session()` pattern**: All ops functions use `with managed_session(session, commit=True) as sess:` instead of the old `_get_session`/try/except/rollback/finally boilerplate. For read-only operations, omit `commit=True`.
