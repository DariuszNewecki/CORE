# src/body/cli/logic/status.py
"""
The presentation layer for the database status command.
This module calls the canonical status service and formats the output for the user.
"""

from __future__ import annotations

from rich.console import Console
from services.repositories.db.status_service import status as get_status_report
from shared.cli_utils import (
    display_error,
    display_info,
    display_success,
    display_warning,
)

console = Console()


# ID: 8b0c8d1d-0f7e-4b3a-8c1d-0f7e8b3a8c1d
async def status():
    """Display database connection and migration status."""
    report = await get_status_report()

    if not report.is_connected:
        display_error("Database connection: FAILED")
        return

    display_success(f"Database connection: OK ({report.db_version})")

    if report.pending_migrations:
        display_warning(f"Found {len(report.pending_migrations)} pending migrations:")
        for mig in report.pending_migrations:
            console.print(f"  - {mig}")
        display_info("Run `core-admin manage database migrate --apply` to apply them.")
    else:
        display_success("Migrations are up to date.")
