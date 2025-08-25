# src/shared/logger.py
"""
CORE's Unified Logging System.

This module provides a single, pre-configured logger instance for the entire
application. It uses the 'rich' library to ensure all output is consistent,
beautifully formatted, and informative.

All other modules should import `getLogger` from this file instead of using
print() or configuring their own loggers.
"""

from __future__ import annotations

import logging

from rich.logging import RichHandler

# --- Configuration ---
LOG_LEVEL = "INFO"
LOG_FORMAT = "%(message)s"
LOG_DATE_FORMAT = "[%X]"  # e.g., [14:30:55]

# --- Prevent duplicate handlers if this module is reloaded ---
# This is crucial for environments like Uvicorn's reloader.
logging.getLogger().handlers = []

# --- Create and configure the handler ---
# The RichHandler will format the output beautifully.
handler = RichHandler(
    rich_tracebacks=True,
    show_time=True,
    show_level=True,
    show_path=False,  # Can be enabled for deeper debugging
    log_time_format=LOG_DATE_FORMAT,
)

# --- Configure the root logger ---
# All loggers created with logging.getLogger(name) will inherit this config.
logging.basicConfig(level=LOG_LEVEL, format=LOG_FORMAT, handlers=[handler])


# CAPABILITY: system_logging
def getLogger(name: str) -> logging.Logger:
    """Returns a pre-configured logger instance with the given name."""
    """
    Returns a pre-configured logger instance.

    Args:
        name (str): The name of the logger, typically __name__ of the calling module.

    Returns:
        logging.Logger: The configured logger.
    """
    return logging.getLogger(name)


# Example of a root-level logger if needed directly
log = getLogger("core_root")
