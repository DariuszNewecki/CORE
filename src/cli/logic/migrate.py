# src/cli/commands/migrate.py
"""
Implements the 'db migrate' command for applying SQL schema changes.
"""
from __future__ import annotations

import asyncio
import pathlib

import typer
from rich.console import Console

from services.repositories.db.common import (  # <-- CORRECTED IMPORT
    apply_sql_file,
    ensure_ledger,
    get_applied,
    load_policy,
    record_applied,
)

console = Console()


async def _run_migrations(apply: bool):
    """The core async logic for running migrations."""
    try:
        pol = load_policy()
        # --- THIS IS THE FIX ---
        # Safely get the migration order and directory, providing empty defaults.
        migrations_config = pol.get("migrations", {})
        order = migrations_config.get("order", [])
        migration_dir = migrations_config.get("directory", "sql")
        # --- END OF FIX ---
    except Exception as e:
        console.print(f"[bold red]❌ Error loading database policy: {e}[/bold red]")
        raise typer.Exit(code=1)

    await ensure_ledger()
    applied = await get_applied()
    pending = [m for m in order if m not in applied]

    if not pending:
        console.print("[bold green]✅ DB schema is up to date.[/bold green]")
        return

    console.print(f"[yellow]Pending migrations found: {pending}[/yellow]")
    if not apply:
        console.print("   -> Run with '--apply' to execute them.")
        return

    for mig in pending:
        console.print(f"   -> Applying migration: {mig}...")
        try:
            await apply_sql_file(pathlib.Path(migration_dir) / mig)
            await record_applied(mig)
            console.print("      [green]...success.[/green]")
        except Exception as e:
            console.print(f"[bold red]      ❌ FAILED to apply {mig}: {e}[/bold red]")
            raise typer.Exit(code=1)

    console.print(
        "[bold green]✅ All pending migrations applied successfully.[/bold green]"
    )


# ID: a6d1df0a-ce85-465a-a29b-6ec422488c2a
def migrate_db(
    apply: bool = typer.Option(False, "--apply", help="Apply pending migrations.")
):
    """Checks for and applies pending database schema migrations."""
    asyncio.run(_run_migrations(apply))
