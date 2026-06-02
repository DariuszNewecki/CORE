# src/cli/resources/database/migrate.py
"""
Database migration command — currently dormant.

The repo operates under a schema-as-truth model: `infra/sql/db_schema_live.sql`
is the canonical schema, regenerated via `pg_dump --schema-only`. One-off SQL
changes are committed under `infra/scripts/migrations/` as historical record
but are NOT replayed through this CLI. The ledger-based migration framework
(MigrationService + core._migrations table) is preserved but unused; this
command will be revived if it is reintroduced. See #438 for history.
"""

from __future__ import annotations

import typer
from rich.console import Console

from cli.utils import core_command

from .hub import app


console = Console()


@app.command("migrate")
@core_command(dangerous=False, requires_context=False)
# ID: d8b7978f-d801-4ba2-a669-f0fd48851b01
async def migrate_database(
    ctx: typer.Context,
    apply: bool = typer.Option(
        False, "--apply", help="(Currently inert — framework is dormant.)"
    ),
) -> None:
    """Show the current migration-framework status.

    Currently dormant: schema-as-truth via `infra/sql/db_schema_live.sql` is
    the canonical model. This command will be revived if ledger-based
    migrations are reintroduced.
    """
    _ = apply  # currently unused; kept for forward-compat
    console.print()
    console.print("[yellow]⏸  Migration framework is currently dormant.[/yellow]")
    console.print()
    console.print("Schema-as-truth model is in effect:")
    console.print("  • Canonical schema:  [cyan]infra/sql/db_schema_live.sql[/cyan]")
    console.print(
        "  • Regenerate via:    [cyan]pg_dump --schema-only --schema=core[/cyan]"
    )
    console.print(
        "  • One-off SQL files: [cyan]infra/scripts/migrations/[/cyan] (historical record)"
    )
    console.print()
    console.print(
        "This command will be revived if ledger-based migrations are reintroduced."
    )
    console.print("See #438 for the framework-orphan history.")
