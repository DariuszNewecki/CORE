# src/cli/commands/fix/settings_access.py
"""Refactor settings.* imports to DI — thin client over POST /v1/fix/run/fix.settings_access."""

from __future__ import annotations

import logging

import typer
from rich.console import Console

from api.cli import CoreApiClient
from cli.utils import core_command

from . import fix_app


logger = logging.getLogger(__name__)
console = Console()


@fix_app.command("settings-di")
@core_command(dangerous=True, confirmation=True)
# ID: 4bb27cb3-4f2f-4462-8c80-7e57828c2ed1
async def fix_settings_di_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply changes"),
    layers: str = typer.Option("mind,will", "--layers", help="Comma-separated layers"),
) -> None:
    """Refactor settings imports to dependency injection via CoreContext."""
    _ = ctx
    layer_list = [layer.strip() for layer in layers.split(",")]
    client = CoreApiClient()
    initial = await client.run_fix(
        "fix.settings_access", write=write, params={"layers": layer_list}
    )
    run_id = initial.get("run_id")
    if not run_id:
        console.print(f"[red]fix.settings_access failed to dispatch: {initial}[/red]")
        raise typer.Exit(1)
    final = await client._poll_run(run_id)
    if final.get("status") != "completed":
        console.print(
            f"[red]fix.settings_access failed: {final.get('error') or final}[/red]"
        )
        raise typer.Exit(1)

    result_data = (final.get("result") or {}).get("data", {})
    results = result_data.get("results", {})
    total_refactored = 0
    total_failed = 0
    for layer_name, stats in results.items():
        console.print(f"\n[cyan]{layer_name.upper()}[/cyan]:")
        console.print(f"  Files analyzed: {stats.get('analyzed', 0)}")
        console.print(f"  Files refactored: {stats.get('refactored', 0)}")
        total_refactored += stats.get("refactored", 0)
        failed = stats.get("failed", 0)
        total_failed += failed
        if failed:
            console.print(f"  [red]Failed: {failed}[/red]")
    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total refactored: {total_refactored}")
    if total_failed:
        console.print(f"  [red]Total failed: {total_failed}[/red]")
    else:
        console.print("  [green]✅ All files processed successfully[/green]")
