# src/body/cli/commands/fix/clarity.py
"""
Clarity and complexity refactoring commands for the 'fix' CLI group.

Refactored to use the Constitutional CLI Framework (@core_command).
"""

from __future__ import annotations

from pathlib import Path

import typer

from shared.cli_utils import core_command
from shared.context import CoreContext

from . import (
    console,
    fix_app,
    handle_command_errors,
)


@fix_app.command("clarity", help="Refactors a file for clarity.")
@handle_command_errors
@core_command(dangerous=True, confirmation=True)
# ID: 0047607b-cc16-46dd-82c1-45e3c7277f44
async def fix_clarity_command(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ..., help="Path to the Python file to refactor.", exists=True, dir_okay=False
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply the refactoring to the file."
    ),
) -> None:
    """
    Uses an AI Architect to refactor code for improved readability.
    """
    core_context: CoreContext = ctx.obj

    with console.status(f"[cyan]Refactoring {file_path} for clarity...[/cyan]"):
        # Using the internal async implementation directly
        # Note: _fix_clarity in the service file currently has an asyncio.run wrapper
        # for legacy calls, but we should call the logic.
        # Looking at previous context, _fix_clarity calls _async_fix_clarity via run.
        # Ideally we'd call _async_fix_clarity directly if exposed, or just call the wrapper.
        # Since we are in an async context provided by @core_command, calling a sync wrapper
        # that calls asyncio.run is bad (nested loops).

        # To fix this properly without editing the service file right now, we can
        # use to_thread if the service is sync blocking, but here the service creates a loop.
        # OPTIMAL FIX: We assume the service exposes the async version or we just call the sync one
        # if it handles its own loop management correctly (though inefficient).
        #
        # Better: We act as a good citizen and use the sync wrapper for now,
        # knowing `core_command` handles the top level loop.
        # Wait, if `core_command` runs us in a loop, and `_fix_clarity` runs `asyncio.run`, it will crash.

        # Let's assume we need to import the async version if possible.
        from features.self_healing.clarity_service import _async_fix_clarity

        await _async_fix_clarity(
            context=core_context, file_path=file_path, dry_run=not write
        )

    console.print("[green]✅ Clarity refactoring completed[/green]")


@fix_app.command(
    "complexity", help="Refactors complex code for better separation of concerns."
)
@handle_command_errors
@core_command(dangerous=True, confirmation=True)
# ID: f876296e-4f59-4729-871e-b9f14298a4b6
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
    """
    Identifies and refactors complexity outliers.
    """
    core_context: CoreContext = ctx.obj

    # Similar import fix for complexity service
    from features.self_healing.complexity_service import _async_complexity_outliers

    with console.status(f"[cyan]Refactoring {file_path} for complexity...[/cyan]"):
        await _async_complexity_outliers(
            cognitive_service=core_context.cognitive_service,
            file_path=file_path,
            dry_run=not write,
        )

    console.print("[green]✅ Complexity refactoring completed[/green]")
