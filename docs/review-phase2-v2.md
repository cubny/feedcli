# Code Review: Phase 2 (v2 — Follow-up)

All 11 issues from the previous review (`review-phase2.md`) have been addressed.
This document summarises what changed and flags a small number of remaining concerns.

---

## Previous Issues — All Resolved

| # | Issue | Resolution |
|---|---|---|
| 1 | `get_items` soft-delete filter unconfirmed | Pre-exists in base code; confirmed by passing tests |
| 2 | `feeds_retry` bypassed `ops.py` | Moved to `reset_feed_errors()` ops function |
| 3 | LIKE wildcards unescaped in `search_items` | Escapes `%`, `_`, `!` with `escape="!"` |
| 4 | `import_opml` swallowed all `ValueError` | Checks `"already exists"` for silent skip; logs warning otherwise |
| 5 | `daemon start` blocks terminal undocumented | Docstring now explains foreground behaviour and `&` / supervisor usage |
| 6 | `_write_toml` silently corrupted deep nesting | Now raises `ValueError` for depth > 1 |
| 7 | `feeds_add --tag` supported only one tag | `multiple=True` with `list(tag)` conversion |
| 8 | `db_vacuum` used `__import__` inline | `sa_text` imported at module level |
| 9 | Unused `ctx` in `feeds_discover` | `@click.pass_context` and `ctx` removed |
| 10 | `config_set` accepted arbitrary keys | `_VALID_CONFIG_KEYS` guard added in CLI |
| 11 | `tags_list` table format broke on `list[str]` | Wraps as `[{"tag": t} ...]` for table path |

New tests were also added covering: `reset_feed_errors`, LIKE wildcard escaping,
`save_config` / `_write_toml`, and OPML duplicate-skip behaviour.

---

## Remaining Concerns

### 1. `db_info` counts starred items including soft-deleted ones (ops.py:952)

```python
starred_count = sess.query(Item).filter(Item.is_starred == True).count()
```

Unlike `unread_count` (which filters `Item.deleted == False`), `starred_count`
includes deleted items. Add `Item.deleted == False` to the filter for consistency.

### 2. `TestResetFeedErrors` patches `feedcli.ops.fetch_feed` — may not work (test_ops.py:1302)

```python
with patch("feedcli.ops.fetch_feed", return_value=0):
```

`reset_feed_errors` calls `update_feed`, which calls `fetch_feed`. Whether this
patch lands depends on how `fetch_feed` is imported in `ops.py`. If it's imported
as `from feedcli.fetcher import fetch_feed`, the name `feedcli.ops.fetch_feed`
must exist in the `ops` module namespace for the patch to intercept it. Verify
the import style; if it's imported at the top of `ops.py`, the patch is correct.

### 3. `import_opml` duplicate check is a string-match on the error message (ops.py:896)

```python
if "already exists" in str(e):
    continue
```

This is a brittle contract. If the error message in `add_feed` changes, duplicates
will stop being silently skipped and will instead emit a log warning. Consider
raising a dedicated exception type (e.g. `FeedAlreadyExistsError`) or returning
a sentinel value from `add_feed` for the duplicate case.

### 4. `test_save_config_creates_file` imports `_xdg_config_home` but doesn't use it (test_ops.py:1335)

```python
from feedcli.config import _xdg_config_home, save_config
```

`_xdg_config_home` is unused in the test body. Remove it to keep the import clean.

### 5. `reset_feed_errors` closes the session before calling `update_feed` when session is None

```python
finally:
    if should_close:
        sess.close()      # ← session closed here
return update_feed(feed_id, session=session)   # ← session=None passed again
```

When the caller passes `session=None`, the internal session is closed in `finally`,
then `update_feed(feed_id, session=None)` creates a fresh session. This is correct
and safe. However, if the caller passes an explicit session, the error-state reset
and the fetch happen in two separate `sess.commit()` calls on the same session —
also fine. This is worth a comment to explain the two-phase commit intentionally.

---

## Tests Coverage Check

All major new ops functions now have unit tests. CLI commands (feeds retry, config
set validation, daemon, OPML import/export) still lack CLI-layer tests via
`CliRunner`, but ops-layer coverage is comprehensive.

---

## Summary

The code is in good shape and ready to merge. The only actionable items before
merging are:

1. Add `Item.deleted == False` to `starred_count` in `db_info` (trivial one-liner)
2. Verify the `patch("feedcli.ops.fetch_feed")` patch target is correct in `TestResetFeedErrors`

Items 3–5 are low-priority and can be addressed as follow-up.
