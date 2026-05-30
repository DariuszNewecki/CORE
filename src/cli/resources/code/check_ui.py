# src/cli/resources/code/check_ui.py
"""
Code UI Compliance Action.
Ensures Body-layer modules are HEADLESS (no print, rich, or direct os.environ).
"""

from __future__ import annotations

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from .hub import app


console = Console()


@app.command("check-ui")
@core_command(dangerous=True, requires_context=False)
# ID: 662d6bed-c6fc-4120-ae34-d9063f703994
async def check_ui_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Use LLM to autonomously fix UI contract violations."
    ),
) -> None:
    """
    Check and repair Body-layer UI contract violations.

    Validates that logic in features/ and services/ does not use:
    - print() or input()
    - rich.console or formatting
    - os.environ (must use shared.config.settings)

    If --write is used, CORE invokes an AI specialist to refactor the
    violating modules into a headless state.
    """
    client = CoreApiClient()
    if not write:
        console.print("[bold cyan]🔍 Checking Body UI Contracts...[/bold cyan]")
        result = await client.quality_body_ui()
        if result.get("status") == "ok":
            console.print("[green]✓ Body UI contracts clean.[/green]")
            return
        violations = result.get("violations", [])
        console.print(f"\n[red]❌ Found {len(violations)} contract violations.[/red]")
        console.print("[yellow]💡 Run with '--write' to auto-fix via LLM.[/yellow]")
        raise typer.Exit(1)
    console.print("[bold cyan]🔧 Refactoring UI leaks out of Body layer...[/bold cyan]")
    initial = await client.run_fix("fix.body_ui", write=True)
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]fix.body_ui failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(f"[red]fix.body_ui failed: {final.get('error') or final}[/red]")
        raise typer.Exit(1)
    console.print("[green]✓ fix.body_ui completed.[/green]")
