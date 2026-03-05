# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Maintenance Policy

**This file must be kept up to date.** After every change to the codebase:
1. Update this file and `AGENTS.md` with any new files, changed APIs, new commands, or architectural decisions.
2. Add lessons learned under the "Lessons Learned" section to avoid repeating mistakes.
3. If `feedcli/ops/` function signatures change, note the breaking change and what downstream consumers (AI agent skills) need to update.

## What is feedcli

feedcli is a local Python library + CLI for RSS/Atom/JSON-Feed management. It stores feeds and items in a local SQLite database, fetches and parses feeds, and exposes a programmatic API (`feedcli.ops`) for external consumers. It uses zero LLM tokens — all operations are deterministic CRUD and HTTP fetching.

External consumers (AI agents, scripts, other tools) import `feedcli.ops` directly as a Python library to power content curation workflows.

## Commands

```bash
# Install
pip install -e .              # Core dependencies
pip install -e ".[dev]"       # With dev dependencies (pytest, ruff, respx)

# Run
feedcli feeds list             # CLI usage
feedcli feeds add <url>        # Add a feed
feedcli items list --unread    # List unread items
feedcli feeds update --all     # Fetch new items from all feeds

# Test
pytest                         # All tests (112 tests)
pytest tests/test_fetcher.py   # Single file
pytest -v                      # Verbose

# Lint
ruff check .                   # Check
ruff check . --fix             # Auto-fix
```

## Architecture

feedcli is a **library-first CLI** — the CLI is a thin wrapper around the `feedcli.ops` package, which is the primary programmatic API.

### Core Components

- **`feedcli/ops/`**: High-level operations API package. Primary interface for CLI and external consumers (AI agent skills). Split into domain modules: `feeds.py`, `items.py`, `categories.py`, `tags.py`, `opml.py`, `config.py`, `database.py`. The `__init__.py` re-exports all public symbols for backward compatibility (`from feedcli.ops import add_feed` still works). All functions accept an optional `session` parameter.

- **`feedcli/ops/_session.py`**: `managed_session()` context manager — replaces the old `_get_session` + try/except/rollback/finally boilerplate. Use `commit=True` for write operations.

- **`feedcli/models.py`**: SQLAlchemy ORM models — `Feed`, `Item`, `Category`, `ItemTag`. Includes composite indexes (`ix_items_feed_unread`), unique constraints (`uq_item_feed_guid`, `uq_item_tag`).

- **`feedcli/db.py`**: Engine and session factory with `get_engine()`, `get_session()`, `reset_engine()`. Auto-creates tables on first use. Uses global `_engine`/`_SessionFactory` singletons.

- **`feedcli/discovery.py`**: Feed URL discovery implementing: direct probe → HTML `<link>` tags → well-known paths → common endpoints → validate with feedparser → deduplicate.

- **`feedcli/fetcher.py`**: Single-threaded feed fetcher (MVP). Uses httpx + feedparser. Conditional GET (ETag/Last-Modified). Deduplicates by `(feed_id, guid)` fallback `(feed_id, url)`. Records errors in `last_error`/`error_count`.

- **`feedcli/cli.py`**: Click CLI entrypoint (`main`). Groups: `feeds` (list/add/delete/update), `items` (list/show/mark-read). JSON default output. Session passed via `click.Context`.

- **`feedcli/config.py`**: XDG-compliant config loading from `$XDG_CONFIG_HOME/feedcli/config.toml` with env var overrides.

- **`feedcli/utils.py`**: `parse_date()` (dateutil-based) and `normalize_url()` helpers.

- **`skill/`**: AI agent skill plugin. Contains `SKILL.md` (agent-facing docs), `skill.yaml` (skill config), `tools.py` (callable functions that wrap `ops.py` and return plain strings).

### Key Patterns

- **Library-first**: `feedcli.ops` package is the primary API. CLI and AI agent skills both consume it. All functions return ORM objects, not formatted strings.
- **Session management**: All ops functions accept optional `session`. If omitted, `managed_session()` creates and closes its own session. For write operations, use `commit=True`.
- **JSON output by default**: CLI defaults to `--format json` for machine consumption.
- **No LLM dependency**: Pure Python, no model calls. Deterministic operations only.
- **Single-user, local-only**: No auth, no multi-tenancy. SQLite file database.
- **HTTP mocking in tests**: Use `respx` for httpx mocking (fetcher, discovery). Use `unittest.mock.patch` for ops-level mocking. Patch at domain module level (e.g., `feedcli.ops.feeds._discover_feeds`), not at `feedcli.ops`.

## Development Policies

- **Testing required**: Every feature needs tests. Use pytest with `:memory:` SQLite DBs. Test fixtures in `tests/fixtures/`.
- **Lint before done**: Always run `ruff check .` after changes. Fix all errors before considering work complete.
- **Commit/push policy**: Always ask for explicit permission before committing or pushing.
- **Plan before implement**: For non-trivial features, provide plan first and wait for approval.
- **Library API stability**: Changes to `feedcli.ops` function signatures affect AI agent skills — be careful with breaking changes.
- **Update docs after changes**: Update this file and `AGENTS.md` after every significant change.

## Test Structure

```
tests/
├── conftest.py              # Shared fixtures: db_session, sample_rss/atom/page
├── fixtures/
│   ├── sample_rss.xml       # 2-item RSS 2.0 feed
│   ├── sample_atom.xml      # 2-entry Atom feed (with content element)
│   ├── sample_page.html     # HTML with <link rel="alternate"> tags
│   └── sample_page_no_feeds.html
├── test_ops.py              # 83 tests — CRUD lifecycle, mark read, dedup, categories, tags
├── test_fetcher.py          # 9 tests — parsing, dedup, conditional GET, errors
├── test_discovery.py        # 5 tests — direct probe, HTML links, well-known paths
└── test_cli.py              # 11 tests — CLI commands via CliRunner, JSON output
```

## Configuration

Environment variables or config file at `~/.config/feedcli/config.toml`:

```
FEEDCLI_DB_PATH=~/.local/share/feedcli/feedcli.db
FEEDCLI_FETCH_TIMEOUT=30
FEEDCLI_FETCH_JOBS=4
```

Python 3.10+ required (3.12+ recommended).

## Current Status

**MVP complete.** Implemented features:
- Feed CRUD (add/list/delete with discovery)
- Feed fetching (single-threaded, conditional GET, error tracking)
- Item listing (all/unread/by-feed, with limit)
- Mark read (single item, by feed, all)
- CLI with JSON/table output
- 112 passing tests, 0 lint errors

**Not yet implemented** (Phase 2+): parallel fetching, search, star/bookmark, tags CLI, OPML, daemon, soft-delete CLI, config CLI, db management CLI.

## Spec

See `docs/spec.md` for the full implementation specification.

## Lessons Learned

- **ruff import sorting**: ruff enforces import sorting (rule I001). Third-party imports from different packages must be in a single sorted block — don't separate `from sqlalchemy` and `from click.testing` with blank lines. Run `ruff check . --fix` to auto-fix.
- **Line length 100**: `pyproject.toml` sets `line-length = 100`. Long docstrings and test invocations can exceed this — break them across lines.
- **`datetime.utcnow()` deprecation**: Python 3.12+ warns about `datetime.utcnow()`. Currently used throughout; consider migrating to `datetime.now(datetime.UTC)` in a future cleanup pass.
- **respx for httpx mocking**: Use `respx` (not `responses` which is for `requests`). Decorate test methods with `@respx.mock` and use `respx.get().mock()`.
- **SQLAlchemy boolean filters**: Use `Filter(Model.field == False)` with `# noqa: E712` to suppress ruff's `==` vs `is` warning — SQLAlchemy requires `==` for SQL generation.
- **ops/ package refactor**: `feedcli/ops.py` was split into `feedcli/ops/` package with domain modules. The `__init__.py` re-exports everything for backward compat. Mock patches must target the domain module (e.g., `feedcli.ops.feeds._discover_feeds`), not `feedcli.ops`.
- **`managed_session()` pattern**: All ops functions use `with managed_session(session, commit=True) as sess:` instead of the old `_get_session`/try/except/rollback/finally boilerplate. For read-only operations, omit `commit=True`.
