# src/cli/resources/project/onboard.py
from pathlib import Path

import typer
from rich.console import Console

from cli.logic.byor import initialize_repository
from cli.utils import core_command
from shared.context import CoreContext

from . import app


console = Console()


@app.command("onboard")
@core_command(dangerous=True, requires_context=True)
# ID: e625b650-05c8-421e-9cf7-073917b43dc9
async def onboard_project(
    ctx: typer.Context,
    path: Path = typer.Argument(..., help="Path to existing repository.", exists=True),
    write: bool = typer.Option(
        False, "--write", help="Write .intent/ directory to the target path."
    ),
) -> None:
    """
    Onboard an existing repository into CORE governance (BYOR).

    Delivers the authored starter constitution (machinery floor + the four-rule
    starter) into the target's .intent/. Does not generate a constitution from
    the target's code (ADR-111). Dry-run by default; pass --write to apply.
    """
    core_context: CoreContext = ctx.obj
    mode = "Onboarding" if write else "Previewing onboarding for"
    console.print(f"[bold cyan]⚓ {mode} repository at:[/bold cyan] {path}")
    await initialize_repository(context=core_context, path=path, dry_run=not write)
