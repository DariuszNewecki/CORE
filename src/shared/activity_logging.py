# src/shared/activity_logging.py
"""
Unified activity logging for CORE workflows.

Provides:
- ActivityRun: correlation info for a single workflow execution
- activity_run(): context manager for wrapping a workflow with start/end logs
- log_activity(): helper to emit structured activity events

This is intentionally generic and can be used by:
- check.audit
- context.build / context.rebuild
- coverage.remediate
- future A2 orchestrators
"""

from __future__ import annotations

import contextlib
import time
import uuid
from collections.abc import Generator
from dataclasses import dataclass
from typing import Any, Literal

from shared.logger import getLogger

logger = getLogger(__name__)

ActivityStatus = Literal["start", "ok", "warning", "error", "skipped"]


@dataclass(frozen=True)
# ID: d5a1bf85-27bd-4404-a51a-4c78a02a20fd
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
    - workflow_start / workflow_complete / phase:* → INFO
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

    # Decide log level
    if event in {"workflow_start", "workflow_complete"} or event.startswith("phase:"):
        log_fn = logger.info
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
    """
    run = new_activity_run(workflow_id)
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
    except Exception as exc:  # noqa: BLE001
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
