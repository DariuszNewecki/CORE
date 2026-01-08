# src/body/cli/commands/fix/clarity.py
# ID: 0047607b-cc16-46dd-82c1-45e3c7277f44

"""
Clarity and complexity refactoring commands for the 'fix' CLI group.
UPGRADED TO V2: Now uses Adaptive Refactoring with Complexity Evaluation.
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


@fix_app.command("clarity", help="Refactors a file for clarity (V2 Adaptive).")
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
    Uses a V2 Adaptive Loop (Analyze -> Strategize -> Refactor -> Evaluate).

    This command will only apply changes if the 'Body' (Evaluator) proves
    that the new code is mathematically less complex or more readable.
    """
    # CONSTITUTIONAL FIX: Lazy-load V2 Orchestrator
    from features.self_healing.clarity_service_v2 import remediate_clarity_v2

    core_context: CoreContext = ctx.obj

    with console.status(f"[cyan]V2 Adaptive Refactoring: {file_path.name}...[/cyan]"):
        # Execute the V2 Cognitive Workflow
        # This replaces the legacy _async_fix_clarity
        await remediate_clarity_v2(
            context=core_context, file_path=file_path, write=write
        )

    if write:
        console.print(
            f"[green]✅ Clarity refactoring cycle completed for {file_path.name}[/green]"
        )
    else:
        console.print(
            f"[yellow]💡 Dry-run complete. Proposed changes evaluated for {file_path.name}[/yellow]"
        )


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
    Identifies and refactors complexity outliers (separation of concerns).
    """
    core_context: CoreContext = ctx.obj

    # CONSTITUTIONAL FIX: Lazy-load service
    from features.self_healing.complexity_service import _async_complexity_outliers

    with console.status(f"[cyan]Refactoring {file_path} for complexity...[/cyan]"):
        await _async_complexity_outliers(
            context=core_context,
            file_path=file_path,
            dry_run=not write,
        )

    console.print("[green]✅ Complexity refactoring completed[/green]")
