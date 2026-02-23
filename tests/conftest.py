"""Shared test fixtures."""

from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from feedcli.models import Base


@pytest.fixture
def db_session():
    """Create an in-memory SQLite session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


@pytest.fixture
def fixtures_dir():
    """Path to test fixtures directory."""
    return Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_rss(fixtures_dir):
    return (fixtures_dir / "sample_rss.xml").read_text()


@pytest.fixture
def sample_atom(fixtures_dir):
    return (fixtures_dir / "sample_atom.xml").read_text()


@pytest.fixture
def sample_page(fixtures_dir):
    return (fixtures_dir / "sample_page.html").read_text()


@pytest.fixture
def sample_page_no_feeds(fixtures_dir):
    return (fixtures_dir / "sample_page_no_feeds.html").read_text()
