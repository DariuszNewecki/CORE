# src/shared/logger.py

"""Centralized logger configuration and factory for the CORE system."""

from __future__ import annotations

import contextvars
import json
import logging
import os
import sys
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from collections.abc import Sequence

# ─────────────────────────────────────────────────────────────── Configuration
_LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
_LOG_FORMAT_TYPE = os.getenv("LOG_FORMAT_TYPE", "human").lower()  # json or human
_VALID_LEVELS = frozenset({"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"})

# Context variable for Activity correlation (Workflow Tracing)
_current_run_id = contextvars.ContextVar("run_id", default=None)

# Validate level at import time
if _LOG_LEVEL not in _VALID_LEVELS:
    logging.warning(f"Invalid LOG_LEVEL '{_LOG_LEVEL}'. Using INFO.")
    _LOG_LEVEL = "INFO"

# ─────────────────────────────────────────────────────────────── Formatters


# ID: d453de4a-8b0a-4dbe-84bb-8bcd78751e15
class JsonFormatter(logging.Formatter):
    """
    Constitutional JSON Formatter (LOG-005).
    Outputs structured logs for machine parsing/aggregation.
    """

    # ID: 7602325a-ebe5-4b21-b25f-043650e8fcf4
    def format(self, record: logging.LogRecord) -> str:
        # Base structured log
        log_record: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),  # Evaluates % args here
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
        }

        # Inject ContextVar (Activity ID) if present
        run_id = _current_run_id.get()
        if run_id:
            log_record["run_id"] = run_id

        # Include exception info if present (LOG-006)
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

        # Merge 'extra' fields into root (LOG-005 compliance)
        # We skip standard LogRecord attributes to avoid clutter
        standard_attrs = {
            "name",
            "msg",
            "args",
            "levelname",
            "levelno",
            "pathname",
            "filename",
            "module",
            "exc_info",
            "exc_text",
            "stack_info",
            "lineno",
            "funcName",
            "created",
            "msecs",
            "relativeCreated",
            "thread",
            "threadName",
            "processName",
            "process",
            "activity",
        }

        for key, value in record.__dict__.items():
            if key not in standard_attrs:
                log_record[key] = value

        # Handle legacy 'activity' dict from shared.activity_logging if present
        if hasattr(record, "activity"):
            log_record["activity"] = record.activity

        return json.dumps(log_record)


# ─────────────────────────────────────────────────────────────── Public API


# ID: 90a8ab6f-c125-43b8-ae6f-e3a8ffc863a8
def getLogger(name: str | None = None) -> logging.Logger:
    return logging.getLogger(name)


# ID: 2021f8a9-f7e0-451c-939d-01d197b517da
def configure_root_logger(
    level: str | None = None,
    handlers: Sequence[logging.Handler] | None = None,
) -> None:
    effective_level = (level or _LOG_LEVEL).upper()
    if effective_level not in _VALID_LEVELS:
        raise ValueError(f"Invalid log level: {effective_level}")

    if handlers is None:
        handlers = []
        # Choose handler based on format type
        if _LOG_FORMAT_TYPE == "json":
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonFormatter())
            handlers.append(handler)
        else:
            # Human-readable (Development)
            try:
                from rich.logging import RichHandler

                handlers.append(
                    RichHandler(
                        rich_tracebacks=True,
                        show_time=True,
                        show_level=True,
                        show_path=False,
                        log_time_format="[%X]",
                    )
                )
            except ImportError:
                handlers.append(logging.StreamHandler())

    logging.basicConfig(
        level=getattr(logging, effective_level),
        handlers=handlers,
        force=True,
    )

    # Suppress noisy external libraries
    for lib in ("httpx", "urllib3", "qdrant_client"):
        logging.getLogger(lib).setLevel(logging.WARNING)


# ID: aa302f01-6997-4e14-b170-2a7e7d3928ea
def reconfigure_log_level(level: str) -> bool:
    try:
        configure_root_logger(level=level)
        getLogger(__name__).info("Log level reconfigured to %s", level.upper())
        return True
    except ValueError:
        return False


# ─────────────────────────────────────────────────────────────── Initialization
configure_root_logger()
logger = getLogger(__name__)
