# src/cli/resources/database/migrate.py
"""
Database migration command.

Runs pending policy-driven migrations via MigrationService.
No Alembic — raw SQL scripts, custom ledger in core._migrations.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from cli.utils import core_command

from .hub import app


logger = logging.getLogger(__name__)
console = Console()


@app.command("migrate")
@core_command(dangerous=True, requires_context=False)
# ID: d8b7978f-d801-4ba2-a669-f0fd48851b01
async def migrate_database(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False, "--apply", help="Apply migrations (default: show pending)"
    ),
) -> None:
    """
    Run pending database migrations.

    Uses policy-driven migration system to apply schema changes.

    Examples:
        # Show pending migrations
        core-admin database migrate

        # Apply all pending migrations
        core-admin database migrate --apply
    """
    console.print("[bold cyan]🔄 Database Migration[/bold cyan]")
    console.print(f"Mode: {'APPLY' if apply else 'PREVIEW'}")
    console.print()
    try:
        from shared.infrastructure.repositories.db.migration_service import (
            MigrationServiceError,
            migrate_db,
        )

        await migrate_db(apply=apply)
        console.print("[green]✅ Migration completed[/green]")
        if not apply:
            console.print()
            console.print("[yellow]💡 Run with --apply to execute migrations[/yellow]")
    except MigrationServiceError as e:
        console.print(f"[red]❌ Migration failed: {e}[/red]")
        raise typer.Exit(e.exit_code)
    except Exception as e:
        logger.error("Migration failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]")
        raise typer.Exit(1)
