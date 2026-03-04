"""SQLAlchemy engine and session factory."""

from __future__ import annotations

from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from feedcli.config import load_config
from feedcli.models import Base

_engine = None
_SessionFactory = None


def _auto_migrate(engine):
    import logging

    from sqlalchemy import inspect, text

    inspector = inspect(engine)
    if "tags" in inspector.get_table_names() and "categories" not in inspector.get_table_names():
        logging.info("Migrating feedcli database from 'tags' to 'categories' schema...")
        with engine.begin() as conn:
            # Create new tables
            conn.execute(
                text("""
                CREATE TABLE categories (
                    id INTEGER PRIMARY KEY,
                    name VARCHAR NOT NULL UNIQUE
                )
            """)
            )
            conn.execute(
                text("""
                CREATE TABLE item_tags (
                    id INTEGER PRIMARY KEY,
                    item_id INTEGER NOT NULL,
                    name VARCHAR NOT NULL,
                    FOREIGN KEY(item_id) REFERENCES items(id)
                )
            """)
            )
            conn.execute(text("CREATE INDEX ix_item_tags_name ON item_tags (name)"))
            conn.execute(text("CREATE INDEX ix_item_tags_item_id ON item_tags (item_id)"))
            conn.execute(text("CREATE UNIQUE INDEX uq_item_tag ON item_tags (item_id, name)"))

            # Insert default category
            conn.execute(text("INSERT INTO categories (id, name) VALUES (1, 'default')"))

            # Create categories from existing tags
            conn.execute(
                text("""
                INSERT INTO categories (name)
                SELECT DISTINCT name FROM tags WHERE name != 'default'
            """)
            )

            # Create an intermediate table for the new feeds data
            # First, fetch existing feed data and map its tags to categories
            # Since SQLite alter table doesn't support adding FKs easily, we'll recreate feeds
            # and copy data over.
            conn.execute(
                text("""
                CREATE TABLE feeds_new (
                    id INTEGER PRIMARY KEY,
                    url VARCHAR NOT NULL UNIQUE,
                    title VARCHAR,
                    website VARCHAR,
                    etag VARCHAR,
                    last_modified VARCHAR,
                    last_fetched_at DATETIME,
                    last_error VARCHAR,
                    error_count INTEGER,
                    disabled BOOLEAN,
                    created_at DATETIME,
                    category_id INTEGER NOT NULL DEFAULT 1 REFERENCES categories(id)
                )
            """)
            )

            # We need to map old feeds to new category_id.
            # Find the first tag per feed to use as its category_id.
            # Any feed without a tag gets category 1 ('default').
            conn.execute(
                text("""
                INSERT INTO feeds_new (id, url, title, website, etag,
                    last_modified, last_fetched_at, last_error, error_count,
                    disabled, created_at, category_id)
                SELECT f.id, f.url, f.title, f.website, f.etag,
                       f.last_modified, f.last_fetched_at, f.last_error,
                       f.error_count, f.disabled, f.created_at,
                       COALESCE((SELECT c.id FROM tags t JOIN categories c
                                 ON t.name = c.name WHERE t.feed_id = f.id LIMIT 1), 1)
                FROM feeds f
            """)
            )

            # Drop old tables and rename new table
            conn.execute(text("DROP TABLE tags"))
            conn.execute(text("DROP TABLE feeds"))
            conn.execute(text("ALTER TABLE feeds_new RENAME TO feeds"))
            logging.info("Migration complete.")


def get_engine(db_path: str | None = None):
    """Get or create the SQLAlchemy engine."""
    global _engine
    if _engine is None or db_path is not None:
        if db_path is None:
            db_path = load_config()["db_path"]
        if db_path != ":memory:":
            Path(db_path).parent.mkdir(parents=True, exist_ok=True)
        _engine = create_engine(f"sqlite:///{db_path}", echo=False)
        _auto_migrate(_engine)
        Base.metadata.create_all(_engine)

        # Ensure 'default' category exists for fresh installs or memory DBs
        from sqlalchemy import text

        with _engine.begin() as conn:
            conn.execute(text("INSERT OR IGNORE INTO categories (id, name) VALUES (1, 'default')"))
    return _engine


def get_session(db_path: str | None = None) -> Session:
    """Create a new session."""
    global _SessionFactory
    engine = get_engine(db_path)
    if _SessionFactory is None or db_path is not None:
        _SessionFactory = sessionmaker(bind=engine, expire_on_commit=False)
    return _SessionFactory()


def reset_engine():
    """Reset the global engine (for testing)."""
    global _engine, _SessionFactory
    _engine = None
    _SessionFactory = None
