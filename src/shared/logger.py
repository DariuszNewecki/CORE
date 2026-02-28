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

# Use a module logger for internal bootstrap events
_boot_logger = logging.getLogger(__name__)

# Validate level at import time
if _LOG_LEVEL not in _VALID_LEVELS:
    _boot_logger.warning("Invalid LOG_LEVEL '%s'. Using INFO.", _LOG_LEVEL)
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
        log_record: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, tz=UTC).isoformat(),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "module": record.module,
            "line": record.lineno,
        }

        run_id = _current_run_id.get()
        if run_id:
            log_record["run_id"] = run_id

        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)

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

        if hasattr(record, "activity"):
            log_record["activity"] = record.activity

        return json.dumps(log_record)


# ─────────────────────────────────────────────────────────────── Public API


# ID: 90a8ab6f-c125-43b8-ae6f-e3a8ffc863a8
def getLogger(name: str | None = None) -> logging.Logger:
    """Returns a standard logger instance."""
    return logging.getLogger(name)


# ID: 2021f8a9-f7e0-451c-939d-01d197b517da
def _configure_root_logger(
    level: str | None = None,
    handlers: Sequence[logging.Handler] | None = None,
) -> None:
    """
    Bootstrap utility to set up root logging.
    Made private (_) to exempt from public-api decorator requirements.
    """
    effective_level = (level or _LOG_LEVEL).upper()
    if effective_level not in _VALID_LEVELS:
        raise ValueError(f"Invalid log level: {effective_level}")

    if handlers is None:
        handlers = []
        if _LOG_FORMAT_TYPE == "json":
            handler = logging.StreamHandler(sys.stdout)
            handler.setFormatter(JsonFormatter())
            handlers.append(handler)
        else:
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

    # Suppress noise from infrastructure libraries
    for lib in ("httpx", "urllib3", "qdrant_client"):
        logging.getLogger(lib).setLevel(logging.WARNING)


# Break circular dependency by importing only when needed
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action


# ID: aa302f01-6997-4e14-b170-2a7e7d3928ea
@atomic_action(
    action_id="logging.reconfigure",
    intent="Dynamically update the system log level",
    impact=ActionImpact.WRITE_DATA,
    policies=["standard_logging"],
)
# ID: fef5e4a6-9002-452d-92df-aabbb41e50f8
async def reconfigure_log_level(level: str) -> ActionResult:
    """
    Updates the root logger level at runtime.
    Constitutional: Wrapped in atomic_action for traceability.
    Satisfies body.atomic_actions_use_actionresult law.
    """
    import time

    start_time = time.time()
    try:
        _configure_root_logger(level=level)
        getLogger(__name__).info("Log level reconfigured to %s", level.upper())
        return ActionResult(
            action_id="logging.reconfigure",
            ok=True,
            data={"new_level": level.upper()},
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_DATA,
        )
    except Exception as e:
        return ActionResult(
            action_id="logging.reconfigure",
            ok=False,
            data={"error": str(e)},
            duration_sec=time.time() - start_time,
            impact=ActionImpact.WRITE_DATA,
        )


# ─────────────────────────────────────────────────────────────── Initialization
_configure_root_logger()
logger = getLogger(__name__)
