# src/body/cli/resources/database/migrate.py
# ID: cli.resources.database.migrate
"""
Database migration command.

Runs pending Alembic migrations to update schema.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.logger import getLogger

from . import app


logger = getLogger(__name__)
console = Console()


@app.command("migrate")
@core_command(dangerous=True, requires_context=False)
# ID: 2a7f9e3d-5b8c-4a1e-9d6f-3c2b7e8a4f1d
async def migrate_database(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Apply migrations (default: show pending)",
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
        console.print(f"[red]❌ Migration failed: {e}[/red]", err=True)
        raise typer.Exit(e.exit_code)

    except Exception as e:
        logger.error("Migration failed", exc_info=True)
        console.print(f"[red]❌ Error: {e}[/red]", err=True)
        raise typer.Exit(1)
