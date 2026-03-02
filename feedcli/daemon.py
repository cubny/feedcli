"""Background fetch scheduler (daemon) for feedcli."""

from __future__ import annotations

import logging
import os
import signal
import sys
import time
from pathlib import Path

logger = logging.getLogger("feedcli.daemon")


def _pid_file() -> Path:
    """Path to the daemon PID file."""
    from feedcli.config import _xdg_data_home

    return _xdg_data_home() / "feedcli" / "daemon.pid"


def _log_file() -> Path:
    """Path to the daemon log file."""
    from feedcli.config import _xdg_data_home

    return _xdg_data_home() / "feedcli" / "daemon.log"


def start(interval: int = 60) -> None:
    """Start the background fetch daemon.

    Args:
        interval: Minutes between fetches (default: 60).
    """
    pid_path = _pid_file()
    pid_path.parent.mkdir(parents=True, exist_ok=True)

    if pid_path.exists():
        pid = int(pid_path.read_text().strip())
        try:
            os.kill(pid, 0)
            raise RuntimeError(
                f"Daemon already running (PID {pid})"
            )
        except ProcessLookupError:
            pid_path.unlink()

    # Write PID
    pid_path.write_text(str(os.getpid()))

    # Setup logging
    log_path = _log_file()
    logging.basicConfig(
        filename=str(log_path),
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )

    def _cleanup(signum, frame):
        logger.info("Daemon stopping (signal %d)", signum)
        pid_path.unlink(missing_ok=True)
        sys.exit(0)

    signal.signal(signal.SIGTERM, _cleanup)
    signal.signal(signal.SIGINT, _cleanup)

    logger.info("Daemon started (PID %d, interval %dm)", os.getpid(), interval)

    try:
        while True:
            try:
                from feedcli.ops import update_all_feeds

                results = update_all_feeds()
                total = sum(results.values())
                logger.info(
                    "Fetched %d new items across %d feeds",
                    total,
                    len(results),
                )
            except Exception:
                logger.exception("Error in fetch cycle")
            time.sleep(interval * 60)
    finally:
        pid_path.unlink(missing_ok=True)


def stop() -> None:
    """Stop the running daemon."""
    pid_path = _pid_file()
    if not pid_path.exists():
        raise RuntimeError("Daemon is not running")

    pid = int(pid_path.read_text().strip())
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    pid_path.unlink(missing_ok=True)


def status() -> dict:
    """Get daemon status."""
    pid_path = _pid_file()
    if not pid_path.exists():
        return {"running": False}

    pid = int(pid_path.read_text().strip())
    try:
        os.kill(pid, 0)
        return {"running": True, "pid": pid}
    except ProcessLookupError:
        pid_path.unlink(missing_ok=True)
        return {"running": False}


def logs(lines: int = 50) -> str:
    """Read recent daemon log lines."""
    log_path = _log_file()
    if not log_path.exists():
        return "No log file found."

    all_lines = log_path.read_text().splitlines()
    return "\n".join(all_lines[-lines:])
