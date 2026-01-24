# src/body/cli/commands/fix/settings_access.py

"""Provides functionality for the settings_access module."""

from __future__ import annotations

import typer
from rich.console import Console

from features.maintenance.refactor_settings_access import refactor_settings_access
from shared.cli_utils import core_command
from shared.context import CoreContext

from . import fix_app


console = Console()


@fix_app.command("settings-di")
@core_command(dangerous=True, confirmation=True)
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567890
async def fix_settings_di_cmd(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Apply changes"),
    layers: str = typer.Option("mind,will", "--layers", help="Comma-separated layers"),
) -> None:
    """Refactor settings imports to dependency injection via CoreContext."""

    core_context: CoreContext = ctx.obj
    repo_root = core_context.git_service.repo_path
    layer_list = [layer.strip() for layer in layers.split(",")]

    results = await refactor_settings_access(
        repo_path=repo_root,
        layers=layer_list,
        dry_run=not write,
    )

    # Print summary
    total_refactored = 0
    total_failed = 0

    for layer_name, stats in results.items():
        console.print(f"\n[cyan]{layer_name.upper()}[/cyan]:")
        console.print(f"  Files analyzed: {stats['analyzed']}")
        console.print(f"  Files refactored: {stats['refactored']}")

        total_refactored += stats["refactored"]
        total_failed += stats["failed"]

        if stats["failed"]:
            console.print(f"  [red]Failed: {stats['failed']}[/red]")

    console.print("\n[bold]Summary:[/bold]")
    console.print(f"  Total refactored: {total_refactored}")
    if total_failed:
        console.print(f"  [red]Total failed: {total_failed}[/red]")
    else:
        console.print("  [green]✅ All files processed successfully[/green]")
