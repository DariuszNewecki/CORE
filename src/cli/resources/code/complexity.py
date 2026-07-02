# src/cli/resources/code/complexity.py

"""
Code Complexity Resource Action.
Refactors complex code for better separation of concerns using V2.3 Adaptive Loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from cli.utils import core_command

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
    from will.self_healing.complexity_service import ComplexityRemediationService

    core_context: CoreContext = ctx.obj

    await ComplexityRemediationService(context=core_context).remediate(
        file_path=file_path,
        write=write,
    )
