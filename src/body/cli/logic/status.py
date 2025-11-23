# src/body/cli/logic/status.py
"""
Diagnostic logic for 'core-admin inspect status'.

Shows DB connectivity and migration status.
"""

from __future__ import annotations

from rich.console import Console
from rich.table import Table

from services.repositories.db.status_service import StatusReport
from services.repositories.db.status_service import status as db_status

console = Console()


# ID: 3f7fa8bb-6b0a-4e3b-9e9b-4adf1e2f0c11
async def _status_impl() -> None:
    """
    Render a human-readable DB status report to the console.

    This is an internal helper used by CLI wrappers (e.g. `inspect status`,
    `init status`). It delegates the actual health/ledger logic to the
    DB status service in `services.repositories.db.status_service`.
    """
    report: StatusReport = await db_status()

    table = Table(
        title="Database Status",
        show_header=True,
        header_style="bold magenta",
    )
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    # Basic connection info
    table.add_row(
        "Connection",
        "OK" if report.is_connected else "FAILED (see logs for details)",
    )
    table.add_row("DB Version", report.db_version or "N/A")

    # Migration details
    applied = ", ".join(sorted(report.applied_migrations)) or "None"
    pending = ", ".join(report.pending_migrations) or "None"

    table.add_row("Applied Migrations", applied)
    table.add_row("Pending Migrations", pending)

    console.print(table)


# ID: cfa2326f-ec64-4248-90f3-de723ea252ac
async def _get_status_report() -> StatusReport:
    """
    Public helper used by the admin CLI and tests.

    Returns the current database status report without rendering it. The
    CLI command is responsible for turning this into human-readable output.
    """
    return await db_status()
