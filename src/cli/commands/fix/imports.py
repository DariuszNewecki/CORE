# src/cli/commands/fix/imports.py
"""
Import organization command for the 'fix' CLI group — thin client over
POST /v1/fix/run/fix.imports.
"""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from . import fix_app


logger = logging.getLogger(__name__)
console = Console()


@fix_app.command(
    "imports",
    help="Sort and group imports according to PEP 8 (stdlib → third-party → local).",
)
@core_command(dangerous=False)
# ID: da8cd296-1100-48b8-b87a-1edeafa5db15
async def fix_imports_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write/--dry-run", help="Apply import sorting (default: dry-run)"
    ),
) -> None:
    """
    Sort and group Python imports according to constitutional style policy.

    Dispatches fix.imports via POST /v1/fix/run/{fix_id}. The server runs
    ruff with the I rules; the CLI polls and reports.
    """
    _ = ctx
    console.print("[bold cyan]Sorting imports...[/bold cyan]")
    console.print(f"Mode: {'WRITE' if write else 'DRY RUN'}")
    client = CoreApiClient()
    initial = await client.run_fix("fix.imports", write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]fix.imports failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]fix.imports failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)
    console.print("[green]✅ Import sorting completed[/green]")
