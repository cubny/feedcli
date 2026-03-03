# Implementation Prompt for Claude Code

Copy the content below the separator line and paste it as your first message to Claude Code (Opus 4.6) in the feedcli repo.

---

I need you to implement the MVP of feedcli — a local Python library + CLI for RSS/Atom/JSON-Feed management. Read `CLAUDE.md`, `AGENTS.md`, and `docs/spec.md` thoroughly before writing any code. The spec is your source of truth.

## What to build (MVP scope only)

Implement exactly what's listed under **MVP** in the Milestones section of `docs/spec.md`:

1. **`pyproject.toml`** — Project config with hatch or poetry. Include all dependencies from the tech stack section. Define `feedcli = "feedcli.cli:main"` as console script. Include `[dev]` extras with pytest and ruff.

2. **`feedcli/db.py`** — SQLAlchemy engine and session factory. Default DB path respecting XDG (`$XDG_DATA_HOME/feedcli/feedcli.db`, fallback `~/.local/share/feedcli/feedcli.db`). Auto-create tables on first use.

3. **`feedcli/models.py`** — SQLAlchemy ORM models for `Feed`, `Item`, and `Tag` exactly as specified in the Database Schema section. Include all indexes and constraints.

4. **`feedcli/config.py`** — XDG-compliant config loading from `$XDG_CONFIG_HOME/feedcli/config.toml` with env var overrides (`FEEDCLI_DB_PATH`, `FEEDCLI_FETCH_TIMEOUT`, `FEEDCLI_FETCH_JOBS`).

5. **`feedcli/discovery.py`** — Feed discovery implementing the algorithm in the spec: direct probe → HTML link tags → well-known paths → common endpoints → validate with feedparser → deduplicate.

6. **`feedcli/fetcher.py`** — Single-threaded feed fetcher using httpx + feedparser. Deduplicate items by `(feed_id, guid)` fallback `(feed_id, url)`. Populate both `summary` and `content` fields from feed entries. Update feed-level `last_fetched_at`. Record errors in `last_error`/`error_count`.

7. **`feedcli/ops.py`** — High-level operations API. For MVP implement: `add_feed`, `list_feeds`, `delete_feed`, `update_feed`, `update_all_feeds`, `get_unread_items`, `get_items`, `get_item`, `mark_read`, `mark_all_read`. All functions take an optional `session` parameter. This is the primary interface — the CLI and Nova skill both consume it.

8. **`feedcli/utils.py`** — Helpers for date parsing/normalization and URL normalization.

9. **`feedcli/cli.py`** — Click CLI with these commands:
   - `feedcli feeds list [--format json|table]`
   - `feedcli feeds add <url> [--title T] [--no-discover] [--auto]`
   - `feedcli feeds delete <feed-id> [--force]`
   - `feedcli feeds update [<feed-id>] [--all]`
   - `feedcli items list [--feed <feed-id>] [--unread] [--limit N] [--format json|table]`
   - `feedcli items show <item-id> [--format json|table]`
   - `feedcli items mark-read <item-id>` / `--feed <feed-id>` / `--all`

   JSON is the default output format. Use `click.Context` to pass the DB session.

10. **Tests** — pytest tests in `tests/`:
    - `test_ops.py`: Test full CRUD lifecycle using `:memory:` SQLite DB. Test add_feed (mock HTTP), list_feeds, delete_feed, get_unread_items, mark_read, mark_all_read.
    - `test_fetcher.py`: Test feed parsing with static XML/Atom fixtures (create a `tests/fixtures/` dir with sample feeds). Test deduplication logic.
    - `test_discovery.py`: Test discovery with recorded HTML samples containing various `<link rel="alternate">` configurations.
    - `test_cli.py`: Test CLI commands using Click's `CliRunner`. Verify JSON output format.

## Implementation guidelines

- Follow the architecture described in CLAUDE.md: library-first, ops.py is the primary API, CLI is a thin wrapper.
- Keep it simple. No async yet (that's Phase 4). Single-threaded fetcher for MVP.
- Use httpx (not requests) for HTTP — it matches Nova's stack and has a sync API.
- For tests, use `pytest-httpserver` or `responses`/`respx` to mock HTTP calls. Never make real network calls in tests.
- Create a `.gitignore` for Python projects.
- After implementation, run `pytest -v` to verify all tests pass, then run `ruff check .` to verify no lint issues.
- Do NOT implement anything beyond MVP scope (no tags CLI, no star CLI, no daemon, no OPML, no parallel fetching). Those are Phase 2+.
- Do NOT commit or push. Just implement and verify tests pass.
