# src/body/cli/commands/fix/docstrings.py
"""
Docstring-related self-healing commands for the 'fix' CLI group.

Provides:
- fix docstrings
"""

from __future__ import annotations

import typer

from features.self_healing.docstring_service import fix_docstrings
from shared.cli_utils import async_command
from shared.context import CoreContext

from . import (
    _confirm_dangerous_operation,
    console,
    fix_app,
    handle_command_errors,
)


@fix_app.command(
    "docstrings", help="Adds missing docstrings using the A1 autonomy loop."
)
@handle_command_errors
@async_command
# ID: f0a66115-bc7a-46bc-a363-d9fa2b283e89
async def fix_docstrings_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Propose and apply the fix autonomously."
    ),
) -> None:
    if not _confirm_dangerous_operation("docstrings", write):
        console.print("[yellow]Operation cancelled by user.[/yellow]")
        return
    core_context: CoreContext = ctx.obj
    with console.status("[cyan]Fixing docstrings...[/cyan]"):
        await fix_docstrings(context=core_context, write=write)
    console.print("[green]✅ Docstring fixes completed[/green]")
