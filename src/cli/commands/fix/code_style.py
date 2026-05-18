# src/cli/commands/fix/code_style.py
"""
Code style and formatting commands for the 'fix' CLI group.

Provides:
- fix headers — thin client over POST /v1/fix/run/fix.headers
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
    "headers", help="Ensures all files have constitutionally compliant headers."
)
@core_command(dangerous=True, confirmation=True)
# ID: 0077efbb-9090-42bb-a602-2ff3b7853875
async def fix_headers_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Apply fixes to files with violations."
    ),
) -> None:
    """
    Dispatches fix.headers via POST /v1/fix/run/{fix_id}.
    """
    _ = ctx
    console.print("[cyan]Checking file headers...[/cyan]")
    client = CoreApiClient()
    initial = await client.run_fix("fix.headers", write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]fix.headers failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]fix.headers failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)
    console.print("[green]✓ fix.headers completed.[/green]")
