# src/body/cli/commands/fix/clarity.py
"""
Clarity and complexity refactoring commands for the 'fix' CLI group.

Provides:
- fix clarity
- fix complexity
"""

from __future__ import annotations

from pathlib import Path

import typer

from features.self_healing.clarity_service import _fix_clarity
from features.self_healing.complexity_service import complexity_outliers
from shared.cli_utils import async_command
from shared.context import CoreContext

from . import (
    _confirm_dangerous_operation,
    console,
    fix_app,
    handle_command_errors,
)


@fix_app.command("clarity", help="Refactors a file for clarity.")
@handle_command_errors
@async_command
# ID: 97d1ae1a-827b-443d-9c38-4b4f0d1f5d6b
async def fix_clarity_command(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ..., help="Path to the Python file to refactor.", exists=True, dir_okay=False
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the refactoring to the file."
    ),
) -> None:
    if not _confirm_dangerous_operation("clarity", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    core_context: CoreContext = ctx.obj
    with console.status(f"[cyan]Refactoring {file_path} for clarity...[/cyan]"):
        await _fix_clarity(context=core_context, file_path=file_path, dry_run=not write)
    console.print("[green]✅ Clarity refactoring completed[/green]")


@fix_app.command(
    "complexity", help="Refactors complex code for better separation of concerns."
)
@handle_command_errors
@async_command
# ID: 18605800-1708-47dc-a631-16cb579e7ed2
async def complexity_command(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ...,
        help="The path to a specific file to refactor for complexity.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the refactoring to the file."
    ),
) -> None:
    if not _confirm_dangerous_operation("complexity", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    core_context: CoreContext = ctx.obj
    with console.status(f"[cyan]Refactoring {file_path} for complexity...[/cyan]"):
        await complexity_outliers(
            context=core_context, file_path=file_path, dry_run=not write
        )
    console.print("[green]✅ Complexity refactoring completed[/green]")
