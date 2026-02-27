# src/body/cli/resources/code/clarity.py
# ID: 3e8a4921-728b-49fc-b83c-d922541d25d0

"""
Code Clarity Resource Action.
Refactors Python code for improved readability using the V2.3 Adaptive Loop.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import typer

from shared.cli_utils import core_command

from .hub import app


if TYPE_CHECKING:
    from shared.context import CoreContext


@app.command("clarity")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: fc72b260-ebc2-4ffc-9194-5e3e192f2a1f
async def clarity_cmd(
    ctx: typer.Context,
    file_path: Path = typer.Argument(
        ...,
        help="Path to the Python file to refactor.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually apply the refactoring to the file."
    ),
) -> None:
    """
    Refactor a file for clarity using the V2.3 Adaptive Loop.

    This command uses a Cognitive Workflow (Analyze -> Strategize -> Refactor -> Evaluate).
    It will only apply changes if the Evaluator proves the code is more readable.
    """
    # CONSTITUTIONAL FIX: Lazy-load orchestrator to prevent circular imports
    from will.self_healing.clarity_service import remediate_clarity

    core_context: CoreContext = ctx.obj

    # Execute the V2 Cognitive Workflow (Will Layer)
    await remediate_clarity(context=core_context, file_path=file_path, write=write)
