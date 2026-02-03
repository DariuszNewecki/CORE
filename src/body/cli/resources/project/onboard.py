# src/body/cli/resources/project/onboard.py
from pathlib import Path

import typer
from rich.console import Console

from body.cli.logic.byor import initialize_repository
from shared.cli_utils import core_command

from . import app


console = Console()


@app.command("onboard")
@core_command(dangerous=True, requires_context=False)
# ID: 59edcd3c-aca7-46e8-8195-681065ee4054
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

    # initialize_repository handles dry_run internally via its own logic
    initialize_repository(path=path, dry_run=not write)
