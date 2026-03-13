# src/cli/resources/database/migrate.py
"""
Database migration command.

Runs pending Alembic migrations to update schema.
"""

from __future__ import annotations

import typer
from rich.console import Console

from shared.cli_utils import core_command
from shared.logger import getLogger

from .hub import app


logger = getLogger(__name__)
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
    logger.info("[bold cyan]🔄 Database Migration[/bold cyan]")
    logger.info("Mode: %s", "APPLY" if apply else "PREVIEW")
    console.print()
    try:
        from shared.infrastructure.repositories.db.migration_service import (
            MigrationServiceError,
            migrate_db,
        )

        await migrate_db(apply=apply)
        logger.info("[green]✅ Migration completed[/green]")
        if not apply:
            logger.info()
            logger.info("[yellow]💡 Run with --apply to execute migrations[/yellow]")
    except MigrationServiceError as e:
        logger.info("[red]❌ Migration failed: %s[/red]", e)
        raise typer.Exit(e.exit_code)
    except Exception as e:
        logger.error("Migration failed", exc_info=True)
        logger.info("[red]❌ Error: %s[/red]", e)
        raise typer.Exit(1)
