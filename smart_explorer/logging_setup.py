from __future__ import annotations

import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Optional

_CONFIGURED = False
_LOG_FILE: Optional[Path] = None


def configure_logging() -> Optional[Path]:
    """
    Configure root logging with both console and rotating file handlers.

    Returns the log file path if file logging is enabled.
    """
    global _CONFIGURED, _LOG_FILE
    if _CONFIGURED:
        return _LOG_FILE

    logging.captureWarnings(True)
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    # Avoid duplicate handlers if configure_logging is called multiple times.
    if root.handlers:
        for handler in list(root.handlers):
            root.removeHandler(handler)

    console_level = _parse_level(os.getenv("SMART_EXPLORER_CONSOLE_LEVEL", "INFO"))
    file_level = _parse_level(os.getenv("SMART_EXPLORER_FILE_LEVEL", "DEBUG"))

    console_handler = logging.StreamHandler()
    console_handler.setLevel(console_level)
    console_handler.setFormatter(_build_formatter())
    root.addHandler(console_handler)

    log_file = _ensure_log_file()
    if log_file:
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=_parse_int(os.getenv("SMART_EXPLORER_LOG_MAX_BYTES"), 2_000_000),
            backupCount=_parse_int(os.getenv("SMART_EXPLORER_LOG_BACKUP_COUNT"), 5),
            encoding="utf-8",
        )
        file_handler.setLevel(file_level)
        file_handler.setFormatter(_build_formatter(include_pid=True))
        root.addHandler(file_handler)
        _LOG_FILE = log_file

    _CONFIGURED = True
    logging.getLogger(__name__).info("Logging initialized. Log file: %s", _LOG_FILE or "stdout only")
    return _LOG_FILE


def get_log_file_path() -> Optional[Path]:
    """Return the path of the active log file, if configured."""
    return _LOG_FILE


def _build_formatter(*, include_pid: bool = False) -> logging.Formatter:
    pieces = ["%(asctime)s", "%(levelname)s", "%(name)s"]
    if include_pid:
        pieces.insert(1, f"PID {os.getpid()}")
    pattern = " | ".join(pieces) + " | %(message)s"
    return logging.Formatter(pattern, datefmt="%Y-%m-%d %H:%M:%S")


def _ensure_log_file() -> Optional[Path]:
    directory = _resolve_log_directory()
    if not directory:
        return None
    try:
        directory.mkdir(parents=True, exist_ok=True)
    except Exception:
        return None
    return directory / "smart_explorer.log"


def _resolve_log_directory() -> Optional[Path]:
    env_dir = os.getenv("SMART_EXPLORER_LOG_DIR")
    if env_dir:
        return Path(env_dir).expanduser()

    if sys.platform.startswith("win"):
        base = Path(os.getenv("LOCALAPPDATA") or Path.home() / "AppData" / "Local")
        return base / "SmartExplorer" / "Logs"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Logs" / "SmartExplorer"

    xdg_state = os.getenv("XDG_STATE_HOME")
    if xdg_state:
        return Path(xdg_state).expanduser() / "smart_explorer"
    return Path.home() / ".local" / "state" / "smart_explorer"


def _parse_level(value: str) -> int:
    try:
        return int(value)
    except Exception:
        return getattr(logging, value.upper(), logging.INFO)


def _parse_int(value: Optional[str], fallback: int) -> int:
    try:
        if value is not None:
            return max(1, int(value))
    except Exception:
        pass
    return fallback


__all__ = ["configure_logging", "get_log_file_path"]
