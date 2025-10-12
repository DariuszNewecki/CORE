# src/cli/logic/status.py
"""
CLI command to check database connectivity and migration status.
This is a thin wrapper around the status service.
"""

from __future__ import annotations

import asyncio

import typer

# This now correctly imports the business logic from the service layer.
from services.repositories.db.status_service import status as get_status_report


# ID: 10235f65-fae8-473a-8a60-f65711b87f43
def status() -> None:
    """Show DB connectivity and migration status by calling the status service."""

    async def _run():
        report = await get_status_report()

        if report.is_connected and report.db_version:
            typer.echo(f"✅ Connected: {report.db_version}")
        else:
            typer.echo("❌ Connection failed.", err=True)
            raise typer.Exit(code=1)

        typer.echo(f"Applied: {sorted(list(report.applied_migrations)) or '—'}")
        typer.echo(f"Pending: {report.pending_migrations or '—'}")

    asyncio.run(_run())
