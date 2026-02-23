"""XDG-compliant configuration loading."""

from __future__ import annotations

import os
from pathlib import Path


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))


def _xdg_data_home() -> Path:
    return Path(os.environ.get("XDG_DATA_HOME", Path.home() / ".local" / "share"))


def get_default_db_path() -> str:
    return str(_xdg_data_home() / "feedcli" / "feedcli.db")


def get_config_path() -> Path:
    return _xdg_config_home() / "feedcli" / "config.toml"


def load_config() -> dict:
    """Load configuration from config file with env var overrides."""
    config = {
        "db_path": get_default_db_path(),
        "fetch_timeout": 30,
        "fetch_jobs": 4,
    }

    config_path = get_config_path()
    if config_path.exists():
        try:
            import tomllib
        except ImportError:
            try:
                import tomli as tomllib  # type: ignore[no-redef]
            except ImportError:
                tomllib = None  # type: ignore[assignment]

        if tomllib is not None:
            with open(config_path, "rb") as f:
                data = tomllib.load(f)
            if "database" in data and "path" in data["database"]:
                config["db_path"] = str(Path(data["database"]["path"]).expanduser())
            if "fetch" in data:
                if "timeout" in data["fetch"]:
                    config["fetch_timeout"] = int(data["fetch"]["timeout"])
                if "jobs" in data["fetch"]:
                    config["fetch_jobs"] = int(data["fetch"]["jobs"])

    # Env var overrides
    if env_db := os.environ.get("FEEDCLI_DB_PATH"):
        config["db_path"] = str(Path(env_db).expanduser())
    if env_timeout := os.environ.get("FEEDCLI_FETCH_TIMEOUT"):
        config["fetch_timeout"] = int(env_timeout)
    if env_jobs := os.environ.get("FEEDCLI_FETCH_JOBS"):
        config["fetch_jobs"] = int(env_jobs)

    return config
