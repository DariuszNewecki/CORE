# src/cli/resources/project/new.py
from shared.logger import getLogger


logger = getLogger(__name__)
import typer
from rich.console import Console

from body.project_lifecycle.scaffolding_service import create_new_project
from cli.utils import core_command
from shared.context import CoreContext

from . import app


console = Console()


@app.command("new")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: 32d44823-26a9-4059-8b64-969a46953225
async def new_project_command(
    ctx: typer.Context,
    name: str = typer.Argument(..., help="The name of the new project."),
    profile: str = typer.Option(
        "default", "--profile", help="Scaffolding template profile."
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually create the directories and files."
    ),
) -> None:
    """
    Scaffold a new CORE-governed application.

    Creates the directory structure and initial .intent/ constitution.
    """
    core_context: CoreContext = ctx.obj
    mode = "Scaffolding" if write else "Previewing"
    logger.info(
        "[bold cyan]🚀 %s project:[/bold cyan] '%s' (Profile: %s)", mode, name, profile
    )
    await create_new_project(
        context=core_context, name=name, profile=profile, write=write
    )
