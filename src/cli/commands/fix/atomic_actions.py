# src/cli/commands/fix/atomic_actions.py
"""
Fix atomic actions pattern violations — thin client over
POST /v1/fix/run/fix.atomic_actions.
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


@fix_app.command("atomic-actions", help="Fix atomic actions pattern violations.")
@core_command(dangerous=True, confirmation=False)
# ID: d729c8ff-0b0c-4873-85b6-0b8151a4265c
async def fix_atomic_actions_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply fixes."),
) -> None:
    """
    Dispatches fix.atomic_actions via POST /v1/fix/run/{fix_id}.
    """
    _ = ctx
    console.print("[cyan]Healing atomic actions...[/cyan]")
    client = CoreApiClient()
    initial = await client.run_fix("fix.atomic_actions", write=write)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]fix.atomic_actions failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(
            f"[red]fix.atomic_actions failed: {final.get('error') or final}[/red]"
        )
        raise typer.Exit(1)
    console.print("[green]✓ fix.atomic_actions completed.[/green]")
