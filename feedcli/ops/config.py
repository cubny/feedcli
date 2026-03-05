"""Configuration get/set operations."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


def get_config() -> dict:
    """Get current configuration as a dictionary."""
    from feedcli.config import load_config

    return load_config()


def set_config(key: str, value: str) -> None:
    """Set a configuration value."""
    from feedcli.config import save_config

    save_config(key, value)
