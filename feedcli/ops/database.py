"""Database info, vacuum, backup, and restore operations."""

from __future__ import annotations

import logging
import os
import shutil
from pathlib import Path

from sqlalchemy.orm import Session

from feedcli.models import Feed, Item

from ._session import managed_session

log = logging.getLogger(__name__)


def db_info(session: Session | None = None) -> dict:
    """Get database stats: feed count, item count, DB file size, etc."""
    from feedcli.config import load_config

    with managed_session(session) as sess:
        feed_count = sess.query(Feed).count()
        item_count = sess.query(Item).count()
        unread_count = (
            sess.query(Item)
            .filter(
                Item.is_read == False,  # noqa: E712
                Item.deleted == False,  # noqa: E712
            )
            .count()
        )
        starred_count = (
            sess.query(Item)
            .filter(
                Item.is_starred == True,  # noqa: E712
                Item.deleted == False,  # noqa: E712
            )
            .count()
        )

        config = load_config()
        db_path = config["db_path"]

        db_size = None
        if db_path != ":memory:" and os.path.exists(db_path):
            db_size = os.path.getsize(db_path)

        return {
            "db_path": db_path,
            "db_size_bytes": db_size,
            "feed_count": feed_count,
            "item_count": item_count,
            "unread_count": unread_count,
            "starred_count": starred_count,
        }


def db_vacuum() -> None:
    """Compact the SQLite database."""
    from feedcli.db import get_engine

    engine = get_engine()
    # VACUUM must run outside a transaction; AUTOCOMMIT ensures that.
    with engine.execution_options(isolation_level="AUTOCOMMIT").connect() as conn:
        conn.exec_driver_sql("VACUUM")


def db_backup(dest_path: str) -> None:
    """Backup the database to a file."""
    from feedcli.config import load_config

    config = load_config()
    src = config["db_path"]
    if src == ":memory:":
        raise ValueError("Cannot backup an in-memory database")
    if not os.path.exists(src):
        raise ValueError(
            f"Database file not found: {src}. Try running a command first to create the DB."
        )
    shutil.copy2(src, dest_path)


def db_restore(src_path: str) -> None:
    """Restore the database from a backup file."""
    from feedcli.config import load_config
    from feedcli.db import reset_engine

    if not os.path.exists(src_path):
        raise ValueError(f"Backup file not found: {src_path}")

    config = load_config()
    dest = config["db_path"]
    if dest == ":memory:":
        raise ValueError("Cannot restore to an in-memory database")
    # Ensure the destination directory exists (e.g. on a fresh XDG setup).
    Path(dest).parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_path, dest)
    reset_engine()
