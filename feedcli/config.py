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


def save_config(key: str, value: str) -> None:
    """Set a config value and write it to disk.

    Supports dotted keys like 'database.path', 'fetch.timeout'.
    """
    config_path = get_config_path()
    config_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing TOML data
    data: dict = {}
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

    # Set the key (support dotted notation), coercing to correct type.
    _INT_KEYS = {"fetch.timeout", "fetch.jobs"}
    parts = key.split(".")
    target = data
    for part in parts[:-1]:
        target = target.setdefault(part, {})
    # Store numerics as int so _write_toml produces bare integers, not strings.
    target[parts[-1]] = int(value) if key in _INT_KEYS else value

    # Write back as TOML (simple writer, no external dep)
    _write_toml(data, config_path)


def _write_toml(data: dict, path: Path) -> None:
    """Write a simple nested dict as TOML (max 1 level of nesting).

    Raises ValueError if values nested deeper than [section] are found.
    """
    for k, v in data.items():
        if isinstance(v, dict):
            for sk, sv in v.items():
                if isinstance(sv, dict):
                    raise ValueError(
                        f"Config key '{k}.{sk}' is nested too deeply. "
                        "Only one level of TOML sections is supported."
                    )
    lines: list[str] = []
    # Top-level scalars first
    for k, v in data.items():
        if not isinstance(v, dict):
            lines.append(f"{k} = {_toml_value(v)}")
    # Then sections
    for k, v in data.items():
        if isinstance(v, dict):
            lines.append(f"\n[{k}]")
            for sk, sv in v.items():
                lines.append(f"{sk} = {_toml_value(sv)}")
    lines.append("")
    path.write_text("\n".join(lines))


def _toml_value(v) -> str:
    """Format a Python value as a TOML value."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, int):
        return str(v)
    if isinstance(v, float):
        return str(v)
    # Escape backslashes and double-quotes for a valid TOML basic string.
    escaped = str(v).replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'
