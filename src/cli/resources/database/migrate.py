# src/cli/resources/database/migrate.py
"""
Database migration command.

Applies pending SQL migrations recorded in infra/migrations/manifest.yaml
against core._migrations. The schema-as-truth model (infra/sql/db_schema_live.sql)
remains canonical for fresh installs; this ledger handles incremental changes
on existing databases.

Workflow for existing installs (migrations applied manually before the ledger):
    core-admin db migrate --bootstrap   # seed ledger, no SQL executed
    core-admin db migrate               # verify 0 pending (dry run)

Workflow going forward:
    # 1. Write infra/scripts/migrations/YYYYMMDD_description.sql
    # 2. Append filename to infra/migrations/manifest.yaml order list
    # 3. core-admin db migrate --apply
"""

from __future__ import annotations

import typer
from rich.console import Console

from cli.utils import core_command
from shared.infrastructure.repositories.db.migration_service import (
    MigrationServiceError,
    bootstrap_migrations,
    migrate_db,
)

from .hub import app


console = Console()


@app.command("migrate")
@core_command(dangerous=True, requires_context=False)
# ID: d8b7978f-d801-4ba2-a669-f0fd48851b01
async def migrate_database(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Execute pending migrations. Without this flag, only shows pending list.",
    ),
    bootstrap: bool = typer.Option(
        False,
        "--bootstrap",
        help=(
            "Seed core._migrations with the full manifest order without running SQL. "
            "Use once on an existing install where migrations were applied manually."
        ),
    ),
) -> None:
    """Show pending migrations or apply them.

    Dry run (default): prints pending migration IDs from the manifest.
    --apply: executes pending SQL files and records them in core._migrations.
    --bootstrap: records all manifest entries as applied without running SQL.
    """
    try:
        if bootstrap:
            await bootstrap_migrations()
            console.print("[green]Bootstrap complete.[/green] Ledger seeded.")
        else:
            await migrate_db(apply=apply)
            if not apply:
                console.print(
                    "[yellow]Dry run.[/yellow] Pass --apply to execute pending migrations."
                )
    except MigrationServiceError as exc:
        console.print(f"[red]Migration error:[/red] {exc}")
        raise typer.Exit(code=exc.exit_code) from exc
