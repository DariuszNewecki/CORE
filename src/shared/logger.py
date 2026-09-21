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
_current_run_id: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "run_id", default=None
)

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


# ID: 861be117-f86f-416e-bf8a-fef5fb2e6a4b
class HumanFormatter(logging.Formatter):
    """One record, one line: ``<ISO-8601 UTC> <LEVEL> <logger>: <message>``.

    The logic-layer default. It renders nothing: no colour, no wrapping, no
    box drawing — those are a terminal's business and belong to the CLI
    (``architecture.channels.logic_no_terminal_rendering``). Under systemd
    this is what journald stores, so a record is one greppable line; the
    interactive ``core-admin`` swaps in a Rich handler on top (see
    ``cli.logging_ui``).
    """

    default_time_format = "%Y-%m-%dT%H:%M:%S"
    default_msec_format = "%s.%03dZ"

    # ID: 6ce652d8-f3f7-4607-9154-5b9de61c8992
    def __init__(self) -> None:
        super().__init__("%(asctime)s %(levelname)s %(name)s: %(message)s")

    # ID: d6f96bdf-4e98-4885-98cf-ffb2da793041
    def formatTime(self, record: logging.LogRecord, datefmt: str | None = None) -> str:
        stamp = datetime.fromtimestamp(record.created, tz=UTC)
        if datefmt:
            return stamp.strftime(datefmt)
        return f"{stamp.strftime(self.default_time_format)}.{record.msecs:03.0f}Z"


# journald priority per Python level (sd-daemon(3)); anything else is INFO.
_SD_PRIORITY = {
    "CRITICAL": 2,
    "ERROR": 3,
    "WARNING": 4,
    "INFO": 6,
    "DEBUG": 7,
}


# ID: 2d2d7b70-b1a8-4d61-a3ce-8d5ea222e69a
class SdDaemonPrefixFormatter(logging.Formatter):
    """Prefix every line of a record with its sd-daemon priority (``<3>`` …).

    Applied only when stderr is not a terminal — i.e. under systemd, where
    stderr becomes the journal. Without it every line lands at PRIORITY=6
    regardless of level, so ``journalctl -p err`` returns nothing whatever
    happened (measured 2026-09-21: 17,585 of 17,585 daemon entries at 6,
    including the night of 2,302 tracebacks). Each line is prefixed, not
    just the first, because journald assigns priority per line and a
    traceback is many lines. Wraps the real formatter (human or JSON) so the
    payload is unchanged.
    """

    # ID: ab90de81-1279-428b-b753-b7c80f27e7a0
    def __init__(self, inner: logging.Formatter) -> None:
        super().__init__()
        self._inner = inner

    # ID: f504f966-5b5f-41f6-9eab-7201f8ea797c
    def format(self, record: logging.LogRecord) -> str:
        prefix = f"<{_SD_PRIORITY.get(record.levelname, 6)}>"
        text = self._inner.format(record)
        return "\n".join(prefix + line for line in text.split("\n"))


def _stderr_is_tty() -> bool:
    try:
        return bool(sys.stderr.isatty())
    except (AttributeError, ValueError):  # closed or replaced stream
        return False


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
        # Plain stderr handler in both modes. Terminal rendering (Rich) is
        # the CLI's decision, made in cli.logging_ui when a human is on
        # stderr — never here, where every process that imports this module
        # would inherit it (the daemon and API run under systemd and got
        # 80-column Rich wrapping in journald for a year).
        inner: logging.Formatter = (
            JsonFormatter() if _LOG_FORMAT_TYPE == "json" else HumanFormatter()
        )
        handler = logging.StreamHandler(sys.stderr)
        handler.setFormatter(
            inner if _stderr_is_tty() else SdDaemonPrefixFormatter(inner)
        )
        handlers = [handler]

    logging.basicConfig(
        level=getattr(logging, effective_level),
        handlers=handlers,
        force=True,
    )

    # Suppress noise from infrastructure libraries
    for lib in ("httpx", "urllib3", "qdrant_client"):
        logging.getLogger(lib).setLevel(logging.WARNING)


# ID: 7d97f8a7-a7c6-4219-a63e-2ee4ad593586
def apply_log_level(level: str) -> None:
    """
    Set the root logger level at runtime -- the plain primitive.

    For bootstrap/composition-root callers (API lifespan applying the
    DB-held ``LOG_LEVEL``, ADR-052) that run before any ActionExecutor
    exists. ``reconfigure_log_level`` below is the governed wrapper over
    this same primitive for callers inside an executor context; calling
    that one directly raises GovernanceBypassError, which is why lifespan
    must not (#889). Raises ValueError on an unknown level name.
    """
    _configure_root_logger(level=level)


# Break circular dependency by importing only when needed
from shared.action_types import ActionImpact, ActionResult
from shared.atomic_action import atomic_action


@atomic_action(
    action_id="logging.reconfigure",
    intent="Dynamically update the system log level",
    impact=ActionImpact.WRITE_DATA,
    policies=["standard_logging"],
)
# ID: fef5e4a6-9002-452d-92df-aabbb41e50f8
async def reconfigure_log_level(level: str, **kwargs) -> ActionResult:
    """
    Updates the root logger level at runtime.
    Constitutional: Wrapped in atomic_action for traceability.
    Satisfies body.atomic_actions_use_actionresult law.
    """
    import time

    start_time = time.time()
    try:
        apply_log_level(level)
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
