"""SQLAlchemy ORM models for Feed, Item, and Tag."""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import DeclarativeBase, relationship


class Base(DeclarativeBase):
    pass


class Feed(Base):
    __tablename__ = "feeds"

    id = Column(Integer, primary_key=True)
    url = Column(String, unique=True, nullable=False)
    title = Column(String)
    website = Column(String)
    etag = Column(String, nullable=True)
    last_modified = Column(String, nullable=True)
    last_fetched_at = Column(DateTime, nullable=True)
    last_error = Column(String, nullable=True)
    error_count = Column(Integer, default=0)
    disabled = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    category_id = Column(Integer, ForeignKey("categories.id"), nullable=False, default=1)

    category = relationship("Category", back_populates="feeds")
    items = relationship("Item", back_populates="feed", cascade="all, delete-orphan")


class Item(Base):
    __tablename__ = "items"
    __table_args__ = (
        UniqueConstraint("feed_id", "guid", name="uq_item_feed_guid"),
        Index("ix_items_feed_unread", "feed_id", "is_read"),
    )

    id = Column(Integer, primary_key=True)
    feed_id = Column(Integer, ForeignKey("feeds.id"), index=True)
    guid = Column(String, index=True)
    title = Column(String)
    url = Column(String)
    author = Column(String)
    summary = Column(Text)
    content = Column(Text)
    published_at = Column(DateTime, index=True)
    fetched_at = Column(DateTime)
    is_read = Column(Boolean, default=False, index=True)
    is_starred = Column(Boolean, default=False, index=True)
    deleted = Column(Boolean, default=False)

    feed = relationship("Feed", back_populates="items")
    tags = relationship("ItemTag", back_populates="item", cascade="all, delete-orphan")


class Category(Base):
    __tablename__ = "categories"

    id = Column(Integer, primary_key=True)
    name = Column(String, unique=True, nullable=False)

    feeds = relationship("Feed", back_populates="category")


class ItemTag(Base):
    __tablename__ = "item_tags"
    __table_args__ = (
        UniqueConstraint("item_id", "name", name="uq_item_tag"),
        Index("ix_item_tags_name", "name"),
    )

    id = Column(Integer, primary_key=True)
    item_id = Column(Integer, ForeignKey("items.id"), index=True)
    name = Column(String, nullable=False)

    item = relationship("Item", back_populates="tags")
