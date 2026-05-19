# src/cli/resources/project/onboard.py
from pathlib import Path

import typer
from rich.console import Console

from cli.logic.byor import initialize_repository
from cli.utils import core_command

from . import app


console = Console()


@app.command("onboard")
@core_command(dangerous=True, requires_context=False)
# ID: e625b650-05c8-421e-9cf7-073917b43dc9
def onboard_project(
    path: Path = typer.Argument(..., help="Path to existing repository.", exists=True),
    write: bool = typer.Option(
        False, "--write", help="Write .intent/ directory to the target path."
    ),
) -> None:
    """
    Onboard an existing repository into CORE governance (BYOR).

    Analyzes code structure and scaffolds a minimal constitution.
    """
    console.print(f"[bold cyan]⚓ Onboarding repository at:[/bold cyan] {path}")
    initialize_repository(path=path, dry_run=not write)
