"""Helpers for date parsing/normalization and URL normalization."""

from __future__ import annotations

from datetime import datetime
from urllib.parse import urlparse, urlunparse

from dateutil import parser as dateutil_parser


def parse_date(date_str: str | None) -> datetime | None:
    """Parse a date string into a datetime, returning None on failure."""
    if not date_str:
        return None
    try:
        return dateutil_parser.parse(date_str)
    except (ValueError, TypeError):
        return None


def normalize_url(url: str) -> str:
    """Normalize a URL by stripping fragments and trailing slashes."""
    parsed = urlparse(url)
    # Remove fragment, normalize path
    path = parsed.path.rstrip("/") or "/"
    normalized = urlunparse((
        parsed.scheme or "https",
        parsed.netloc,
        path,
        parsed.params,
        parsed.query,
        "",  # no fragment
    ))
    return normalized
