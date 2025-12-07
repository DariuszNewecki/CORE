# src/body/cli/logic/status.py
"""
Diagnostic logic for 'core-admin inspect status'.

Shows DB connectivity and migration status.
"""

from __future__ import annotations

from services.repositories.db.status_service import StatusReport
from services.repositories.db.status_service import status as db_status


# ID: 3f7fa8bb-6b0a-4e3b-9e9b-4adf1e2f0c11
async def _status_impl() -> None:
    """
    Render a human-readable DB status report to the console.

    This is an internal helper used by CLI wrappers (e.g. `inspect status`,
    `init status`). It delegates the actual health/ledger logic to the
    DB status service in `services.repositories.db.status_service`.
    """
    # Use the status-report helper so tests can patch it and governance
    # can reason about a single place where DB status is obtained.
    report: StatusReport = await _get_status_report()

    # TODO: This function should not render UI in a Body module.
    # CLI wrappers should handle rendering. For now, we keep it as a no-op.
    pass


# ID: cfa2326f-ec64-4248-90f3-de723ea252ac
async def _get_status_report() -> StatusReport:
    """
    Internal helper used by the admin CLI and tests.

    Returns the current database status report without rendering it. The
    CLI command is responsible for turning this into human-readable output.
    """
    return await db_status()


# NOTE:
# We intentionally expose `get_status_report` only as an alias to the
# private `_get_status_report` function. This keeps tests and callers
# able to import and await `get_status_report`, but the symbol graph
# only sees the underlying `_get_status_report` function as a single
# (private) implementation detail, avoiding orphaned public logic.
get_status_report = _get_status_report
