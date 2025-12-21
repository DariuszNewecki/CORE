# src/shared/activity_logging.py
"""
Activity logging for workflow execution tracking.

Provides structured logging with correlation IDs for all workflow runs.
Maintains audit trail of all actions and their outcomes.
"""

from __future__ import annotations

import contextlib
import logging
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any

from shared.logger import _current_run_id  # Import the context var


logger = logging.getLogger(__name__)

# Type alias for activity status
ActivityStatus = str  # "start" | "ok" | "error" | "warning"


@dataclass
# ID: 8be33d13-9d87-46d4-a5c2-ef5f1f8f3b5e
class ActivityRun:
    """Correlation info for a single workflow execution."""

    workflow_id: str
    run_id: str


# ID: 0d9d9ca0-6784-4e62-82f7-258643e78675
def new_activity_run(workflow_id: str) -> ActivityRun:
    """Create a new ActivityRun with a generated run_id."""
    return ActivityRun(workflow_id=workflow_id, run_id=str(uuid.uuid4()))


# ID: 67df9d2f-aac0-4b3e-96c1-02da05e8ea87
def log_activity(
    run: ActivityRun,
    event: str,
    status: ActivityStatus,
    message: str | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    """
    Emit a structured activity log event.

    This is a thin wrapper around the standard logger that ensures
    we always include workflow_id + run_id + status + event.

    Logging behaviour:
    - workflow_start / workflow_complete / phase:* → DEBUG (quiet for CLI)
    - status == "warning" → WARNING
    - status == "error"   → ERROR
    - everything else      → DEBUG

    The `extra["activity"]` payload gives future log processors
    a consistent shape to work with.
    """
    payload: dict[str, Any] = {
        "workflow_id": run.workflow_id,
        "run_id": run.run_id,
        "event": event,
        "status": status,
    }
    if message:
        payload["message"] = message
    if details:
        payload["details"] = details

    # Human-readable message instead of just "activity"
    msg = message or f"[{run.workflow_id}] {event} ({status})"

    # Decide log level - workflow events go to DEBUG to keep CLI clean
    if event in {"workflow_start", "workflow_complete"} or event.startswith("phase:"):
        log_fn = logger.debug
    elif status == "warning":
        log_fn = logger.warning
    elif status == "error":
        log_fn = logger.error
    else:
        # Default to DEBUG for low-level noise (e.g. per-check events)
        log_fn = logger.debug

    log_fn(msg, extra={"activity": payload})


@contextlib.contextmanager
# ID: 2491fde3-98b7-4bc0-907a-a4578b201068
def activity_run(
    workflow_id: str,
    details: dict[str, Any] | None = None,
) -> Generator[ActivityRun, None, None]:
    """
    Context manager that logs the start and end of a workflow run.

    Usage:
        with activity_run("check.audit") as run:
            log_activity(run, "phase:knowledge_graph", "start")
            ...

    On exit, it automatically logs workflow completion or error with duration.
    Note: Logs at DEBUG level to keep CLI output clean.
    """
    run = new_activity_run(workflow_id)

    # Set the context var for this block
    token = _current_run_id.set(run.run_id)

    start_time = time.time()

    log_activity(
        run,
        event="workflow_start",
        status="start",
        message=f"Workflow {workflow_id} started",
        details=details,
    )

    try:
        yield run
    except Exception as exc:
        duration = time.time() - start_time
        log_activity(
            run,
            event="workflow_error",
            status="error",
            message=f"Workflow {workflow_id} failed: {exc}",
            details={"duration_sec": duration},
        )
        raise
    else:
        duration = time.time() - start_time
        log_activity(
            run,
            event="workflow_complete",
            status="ok",
            message=f"Workflow {workflow_id} completed successfully",
            details={"duration_sec": duration},
        )
    finally:
        # Clean up context var
        _current_run_id.reset(token)
