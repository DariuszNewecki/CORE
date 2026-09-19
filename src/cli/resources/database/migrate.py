# src/cli/resources/database/migrate.py
"""
Database migration command.

Applies pending SQL migrations recorded in infra/migrations/manifest.yaml
against core._migrations. The canonical schema for a fresh install is the
repository-root ``schema.sql``; this ledger handles incremental changes on
existing databases.

Current behaviour (v2.10.x): ``core-admin database migrate`` without ``--apply``
is a dry run that lists pending migrations and executes nothing.

Upgrading an existing database is currently UNSUPPORTED (ADR-162): no install
or startup path seeds the ledger, so a database created from ``schema.sql``
reports every manifest entry as pending, ``--apply`` would replay history, and
``--bootstrap`` run after switching to a newer checkout records migrations as
applied without executing them. ADR-162 retires ``--bootstrap`` in favour of
verified baseline adoption and makes ``--write`` the mutation flag; those
changes land in later units, not here.

Execution (ADR-162 D7, U2): each pending migration runs in ONE transaction
together with its ``core._migrations`` row, under a fixed advisory lock with
the ledger re-read inside the lock. A failure leaves that migration fully
rolled back and unrecorded; earlier ones stay recorded; re-running is safe.
Files may keep a leading ``BEGIN;`` / trailing ``COMMIT;`` (stripped by the
engine); any other transaction control or non-transactional statement is
refused before anything executes.

Workflow going forward:
    # 1. Write infra/scripts/migrations/YYYYMMDD_description.sql
    # 2. Append filename to infra/migrations/manifest.yaml order list
    # 3. core-admin database migrate --apply
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
            recorded = await bootstrap_migrations()
            console.print(
                f"[green]Bootstrap complete.[/green] {len(recorded)} ledger row(s) seeded."
            )
        else:
            report = await migrate_db(write=apply)
            if not apply:
                console.print(
                    f"[yellow]Dry run.[/yellow] {len(report.pending_before)} pending. "
                    "Pass --apply to execute pending migrations."
                )
            else:
                console.print(
                    f"[green]Migrations complete.[/green] "
                    f"{len(report.applied)} applied, {len(report.reconciled)} reconciled, "
                    f"{len(report.skipped)} skipped."
                )
    except MigrationServiceError as exc:
        console.print(f"[red]Migration error:[/red] {exc}")
        raise typer.Exit(code=exc.exit_code) from exc
