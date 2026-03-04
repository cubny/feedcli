# Code Review: Phase 2 Unstaged Changes

## Overview

Substantial Phase 2 implementation adding: tags, star/bookmark, item management
(mark-unread, soft/hard delete, search), OPML import/export, config management,
DB management CLI, and a background daemon. New files: `feedcli/daemon.py`,
`feedcli/opml.py`. Changes are well-structured and generally follow existing patterns.

---

## Bugs / Correctness Issues

### 1. `test_soft_delete` assumes `get_items` filters deleted items — not visible in diff

`tests/test_ops.py:999` asserts `len(items) == 2` after a soft delete, but the
`get_items` diff only adds the `starred_only` parameter — no `Item.deleted == False`
filter is shown. Either this filter pre-exists (not visible in diff) or the test
will fail. Verify `get_items` excludes `deleted=True` items.

### 2. `feeds_retry` (cli.py:92–96) bypasses `ops.py` — violates library-first principle

```python
feed.error_count = 0
feed.disabled = False
feed.last_error = None
sess.commit()
```

ORM fields are manipulated directly in the CLI layer. Should be a dedicated
`reset_feed_errors(feed_id, session)` ops function, consistent with the
library-first architecture.

### 3. `search_items` — LIKE wildcards in user query are unescaped (ops.py:630)

```python
pattern = f"%{query}%"
```

If the user searches for `100%` or `file_name`, the `%` and `_` are treated as
SQL wildcards, giving surprising results. Not a SQL injection risk (SQLAlchemy
parameterizes), but should escape metacharacters in the query string.

### 4. `import_opml` silently swallows all `ValueError`, not just duplicates (ops.py:827)

```python
except ValueError:
    continue  # Feed already exists, skip
```

Any `ValueError` from `add_feed` is silently skipped — including non-duplicate
errors. Should catch only the specific duplicate case or log a warning for
unexpected errors.

---

## Design Issues

### 5. `daemon start` is a foreground blocking call, not a true daemon (daemon.py:69–85)

`start()` runs a `while True` loop with `time.sleep()` in the foreground. Calling
`feedcli daemon start` blocks the terminal — it does not fork or detach. Users
expecting a background daemon will be confused. Options:
- Document clearly that users must run it with `&` or under a process manager
- Or implement a proper double-fork daemonize

### 6. `_write_toml` only handles one level of nesting (config.py:531)

The writer handles `[section]` but not `[section.subsection]`. Calling
`set_config("a.b.c", "val")` would silently produce incorrect TOML. The function
should either validate depth or use a proper TOML serialization library.

### 7. `feeds_add --tag` only allows a single tag (cli.py:26)

`add_feed` accepts `tags: list[str]`, but the CLI option only takes one value.
Using `multiple=True` on the Click option would allow `--tag tech --tag ai`.

### 8. `db_vacuum` uses `__import__` inline (ops.py:913)

```python
conn.execute(__import__("sqlalchemy").text("VACUUM"))
```

Unnecessarily obscure. `from sqlalchemy import text` should be added to the
module-level imports at the top of `ops.py`.

### 9. `feeds_discover` has an unused `ctx` parameter (cli.py:70)

`ctx` is declared but never used — discovery doesn't need the DB session.
Remove `@click.pass_context` and the `ctx` parameter.

---

## Minor Issues

### 10. `config_set` does not validate known config keys

Any arbitrary dotted key can be written to the config file. At minimum, the
help string should document valid keys, or add a validation step against the
known key set.

### 11. `tags_list` table output may break

`list_tags` returns `list[str]`, but `_output` with `fmt="table"` likely expects
`list[dict]`. Passing a list of strings may error or produce garbled output. The
table format path needs to handle plain string lists.

---

## Tests

- Coverage is thorough and well-organized across all new ops functions.
- `test_search_case_insensitive` correctly relies on `ilike`.
- `TestImportExportOpml.test_export_and_import` correctly patches `_discover_feeds`.

**Missing test coverage:**
- `feeds_retry` CLI (direct ORM manipulation path)
- `daemon` module functions (`start`, `stop`, `status`, `logs`)
- `config.save_config` / `_write_toml` (especially multi-level nesting edge case)
- `feeds_discover` CLI command

---

## Summary

| Severity | Issue |
|---|---|
| Bug | Verify `get_items` excludes soft-deleted items |
| Bug | LIKE wildcards unescaped in `search_items` |
| Bug | `import_opml` swallows all `ValueError`, not just duplicates |
| Architecture | `feeds_retry` CLI manipulates ORM directly — needs an ops function |
| UX | `daemon start` blocks the terminal — not a true daemon |
| Correctness | `_write_toml` only handles 1 level of nesting |
| Minor | `feeds_add --tag` supports only one tag |
| Minor | `db_vacuum` uses `__import__` inline |
| Minor | Unused `ctx` in `feeds_discover` |
| Minor | `tags_list` table format may break on `list[str]` |
| Tests | Missing coverage for daemon, config write, feeds_retry, feeds_discover |
