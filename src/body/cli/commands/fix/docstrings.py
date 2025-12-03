# src/body/cli/commands/fix/docstrings.py
"""
Docstring-related self-healing commands for the 'fix' CLI group.

Provides:
- fix docstrings
"""

from __future__ import annotations

import typer
from features.self_healing.docstring_service import fix_docstrings
from shared.cli_utils import core_command
from shared.context import CoreContext

from . import (
    console,
    fix_app,
    handle_command_errors,
)


@fix_app.command(
    "docstrings", help="Adds missing docstrings using the A1 autonomy loop."
)
@handle_command_errors
@core_command(dangerous=True, confirmation=True)
# ID: 03a9012f-8da6-4431-a586-b83c146b7d2b
async def fix_docstrings_command(
    ctx: typer.Context,
    write: bool = typer.Option(
        False, "--write", help="Propose and apply the fix autonomously."
    ),
) -> None:
    """
    CLI wrapper for fix docstrings.
    """
    # Safety checks and async loop handling are now managed by @core_command

    core_context: CoreContext = ctx.obj

    # JIT wiring ensures cognitive_service is ready for the agent
    with console.status("[cyan]Fixing docstrings...[/cyan]"):
        await fix_docstrings(context=core_context, write=write)

    console.print("[green]✅ Docstring fixes completed[/green]")
