# src/body/cli/resources/code/complexity.py
# ID: f1289e90-c235-46fd-a8c6-52418e912bc3

"""
Code Complexity Resource Action.
Refactors complex code for better separation of concerns using V2.3 Adaptive Loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from shared.cli_utils import core_command

from .hub import app


if TYPE_CHECKING:
    from shared.context import CoreContext


@app.command("complexity")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: 8608b515-e269-4f14-aefe-a8d0904fbcc2
async def complexity_cmd(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ...,
        help="Path to the file to refactor for complexity.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually apply the refactoring to the file."
    ),
) -> None:
    """
    Identify and refactor complexity outliers using the V2.3 Adaptive Orchestrator.

    Targets high cyclomatic complexity and 'God Methods' to improve modularity.
    """
    # CONSTITUTIONAL FIX: Swapped legacy service for V2.3 Roadmap-Compliant logic
    from will.self_healing.complexity_service import remediate_complexity

    core_context: CoreContext = ctx.obj

    # This uses the high-resilience loop similar to 'code clarity'
    await remediate_complexity(
        context=core_context,
        file_path=file_path,
        write=write,
    )
