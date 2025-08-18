# src/shared/logger.py
"""
CORE's Unified Logging System.

Use `configure_logging()` once at process start to set level/format/stream.
Then get contextual loggers with `getLogger(name)` everywhere else.

Intent: Provide consistent, constitutionally governed logging across CLI and API,
with optional JSON mode for production/CI, while keeping human-readable logs by default.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import datetime
from typing import Optional, TextIO


class _JsonFormatter(logging.Formatter):
    """Minimal JSON formatter for structured logs."""

    def format(self, record: logging.LogRecord) -> str:
        """Intent: Render a LogRecord as a compact JSON object suitable for ingestion."""
        payload = {
            "time": datetime.utcfromtimestamp(record.created).isoformat() + "Z",
            "level": record.levelname,
            "name": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "filename": record.filename,
            "lineno": record.lineno,
        }
        return json.dumps(payload, ensure_ascii=False)


def _coerce_level(level: str | int) -> int:
    """Intent: Normalize a user-supplied level (str/int) to a logging.* constant."""
    if isinstance(level, int):
        return level
    return getattr(logging, str(level).upper(), logging.INFO)


def configure_logging(
    *,
    level: str | int = "INFO",
    stream: Optional[TextIO] = None,
    json_mode: Optional[bool] = None,
) -> None:
    """
    Configure root logging.

    Args:
        level: "DEBUG"|"INFO"|"WARNING"|"ERROR" or int.
        stream: Target stream; defaults to real stderr (sys.__stderr__).
        json_mode: True → JSON logs; False → human logs. If None, uses env CORE_LOG_JSON.
    """
    # Decide stream & mode
    stream = stream or sys.__stderr__
    if json_mode is None:
        json_mode = os.getenv("CORE_LOG_JSON", "false").lower() == "true"

    # Build handler
    handler = logging.StreamHandler(stream)
    if json_mode:
        handler.setFormatter(_JsonFormatter())
    else:
        # Keep the classic, readable format seen in tests
        handler.setFormatter(logging.Formatter("%(levelname)s:%(name)s: %(message)s"))

    # Apply to root (force clears previous handlers)
    logging.basicConfig(level=_coerce_level(level), handlers=[handler], force=True)


# CAPABILITY: system_logging
def getLogger(name: str) -> logging.Logger:
    """Return a named logger. Call `configure_logging()` once at startup."""
    logger = logging.getLogger(name)
    # When under pytest, be verbose by default unless overridden by configure_logging
    if "pytest" in sys.modules:
        logger.setLevel(logging.DEBUG)
    return logger


# Optional root-level logger
log = getLogger("core_root")
