# src/shared/logger.py

"""Centralized logger configuration and factory for the CORE system."""

from __future__ import annotations

import logging
import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from collections.abc import Sequence

# ─────────────────────────────────────────────────────────────── Configuration
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_FORMAT = os.getenv("LOG_FORMAT", "%(message)s")
_LOG_DATE_FORMAT = "[%X]"
_VALID_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

# Validate level at import time
if _LOG_LEVEL not in _VALID_LEVELS:
    logging.warning(f"Invalid LOG_LEVEL '{_LOG_LEVEL}'. Using INFO.")
    _LOG_LEVEL = "INFO"

# ─────────────────────────────────────────────────────────────── Handler Setup
try:
    from rich.logging import RichHandler

    _HANDLER = RichHandler(
        rich_tracebacks=True,
        show_time=True,
        show_level=True,
        show_path=False,
        log_time_format=_LOG_DATE_FORMAT,
    )
except ImportError:
    _HANDLER = logging.StreamHandler()
    logging.warning("rich library not found. Using standard logging.")


# ─────────────────────────────────────────────────────────────── Public API
# ID: 71a69dde-6c42-46d2-9055-968e46c7df35
def getLogger(name: str | None = None) -> logging.Logger:
    """
    Return a pre-configured logger instance.

    Args:
        name: Logger name. Defaults to calling module's __name__.

    Returns:
        Configured logging.Logger instance.
    """
    return logging.getLogger(name)


# ID: ba1f990c-8d82-41e4-aca3-2c2607c1f08b
def configure_root_logger(
    level: str | None = None,
    format_: str | None = None,
    handlers: Sequence[logging.Handler] | None = None,
) -> None:
    """
    Configure the root logger. Safe to call multiple times.

    Args:
        level: Override log level. Defaults to LOG_LEVEL env var.
        format_: Override format string. Defaults to LOG_FORMAT env var.
        handlers: Custom handlers. Defaults to RichHandler/StreamHandler.
    """
    effective_level = (level or _LOG_LEVEL).upper()
    if effective_level not in _VALID_LEVELS:
        raise ValueError(f"Invalid log level: {effective_level}")

    logging.basicConfig(
        level=getattr(logging, effective_level),
        format=format_ or _LOG_FORMAT,
        handlers=handlers or [_HANDLER],
        force=True,
    )

    # Suppress noisy external libraries
    _suppress_noisy_loggers()


def _suppress_noisy_loggers() -> None:
    """Restrict logging for known verbose libraries."""
    for lib in ("httpx",):
        logging.getLogger(lib).setLevel(logging.WARNING)


# ID: adb255a4-234c-4f61-8ba3-37239238206d
def reconfigure_log_level(level: str) -> bool:
    """
    Reconfigure the root logger's level at runtime.

    Returns:
        True if successful, False if invalid level.
    """
    try:
        configure_root_logger(level=level)
        getLogger(__name__).info("Log level reconfigured to %s", level.upper())
        return True
    except ValueError:
        return False


# ─────────────────────────────────────────────────────────────── Initialization
configure_root_logger()  # Auto-configure on import

# Module logger for internal use
logger = getLogger(__name__)
