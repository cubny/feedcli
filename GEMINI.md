# GEMINI.md - Project Mandates

This file provides project-specific instructions and technical context for Gemini CLI.

## Core Mandates

1. **Maintain Determinism**: NEVER introduce LLM dependencies or non-deterministic logic into the core library (`feedcli/`). `feedcli` is a data source, not an intelligence layer.
2. **Library-First Integrity**: Any change to CLI functionality MUST be implemented in `feedcli/ops.py` first, then exposed in `feedcli/cli.py`.
3. **Protect the API Surface**: `feedcli/ops.py` is the primary interface for external consumers. Avoid breaking changes to function signatures. If changes are necessary, update `skill/tools.py` accordingly.
4. **Mock All Network Calls**: NEVER make real network requests in tests. Use `@respx.mock` and `respx` for all HTTP mocking.

## Technical Context

### Database & ORM (SQLAlchemy 2.0)
- **Sessions**: Functions in `ops.py` should accept an optional `session` parameter. If not provided, they should use a context manager or session factory to ensure proper resource management.
- **Boolean Comparisons**: Use `Column == True` or `Column == False` for SQLAlchemy filters (not `is`). Add `# noqa: E712` if `ruff` complains.
- **In-Memory Testing**: Use `:memory:` SQLite databases for all unit and integration tests.

### Feed Parsing & Fetching
- **`feedparser`**: Remember that `entry.content` is a list of dictionaries. Access the value via `entry.content[0].value`.
- **HTTP Client**: Use `httpx` for all network operations.
- **Dates**: Use `feedcli.utils.parse_date` for consistency. Be aware of `datetime.utcnow()` deprecations in Python 3.12+; prefer `datetime.now(datetime.UTC)`.

### CLI
- **JSON Default**: CLI commands should default to JSON output to facilitate automation.
- **XDG Compliance**: Respect XDG base directories for config and data via `feedcli.config`.

## Development Workflow

- **Validation**: Always run `pytest` and `ruff check .` before completing a task.
- **Reproduction**: For bug fixes, create a failing test case in `tests/` using the fixtures in `tests/fixtures/` or `respx` mocks.
- **Documentation**: Update `AGENTS.md` and `CLAUDE.md` after any architectural or API changes.

## Testing Commands

```bash
pytest                          # Run all tests
ruff check . --fix             # Lint and auto-fix
ruff format .                  # Format code
```
