# src/services/repositories/db/migration_service.py
"""
Provides the canonical, single-source-of-truth service for applying database schema migrations.
"""

from __future__ import annotations

import asyncio
import pathlib

import typer
from rich.console import Console

from .common import (
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
        migrations_config = pol.get("migrations", {})
        order = migrations_config.get("order", [])
        migration_dir = migrations_config.get("directory", "sql")
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


# ID: 7bb0c5ee-480b-4d14-9147-853c9f9b25c5
def migrate_db(
    apply: bool = typer.Option(False, "--apply", help="Apply pending migrations."),
):
    """Initialize DB schema and apply pending migrations."""
    asyncio.run(_run_migrations(apply))
