# src/cli/commands/fix/settings_access.py
"""Provides functionality for the settings_access module."""

from __future__ import annotations

from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from body.maintenance.refactor_settings_access import refactor_settings_access
from cli.utils import core_command
from shared.context import CoreContext

from . import fix_app


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
    core_context: CoreContext = ctx.obj
    repo_root = core_context.git_service.repo_path
    layer_list = [layer.strip() for layer in layers.split(",")]
    results = await refactor_settings_access(
        repo_path=repo_root, layers=layer_list, dry_run=not write
    )
    total_refactored = 0
    total_failed = 0
    for layer_name, stats in results.items():
        logger.info("\n[cyan]%s[/cyan]:", layer_name.upper())
        logger.info("  Files analyzed: %s", stats["analyzed"])
        logger.info("  Files refactored: %s", stats["refactored"])
        total_refactored += stats["refactored"]
        total_failed += stats["failed"]
        if stats["failed"]:
            logger.info("  [red]Failed: %s[/red]", stats["failed"])
    logger.info("\n[bold]Summary:[/bold]")
    logger.info("  Total refactored: %s", total_refactored)
    if total_failed:
        logger.info("  [red]Total failed: %s[/red]", total_failed)
    else:
        logger.info("  [green]✅ All files processed successfully[/green]")
