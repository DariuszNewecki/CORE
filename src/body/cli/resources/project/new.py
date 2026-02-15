# src/body/cli/resources/project/new.py
import typer
from rich.console import Console

# UPDATED: Import from body instead of features
from body.project_lifecycle.scaffolding_service import create_new_project
from shared.cli_utils import core_command
from shared.context import CoreContext

from . import app


console = Console()


@app.command("new")
@core_command(dangerous=True, requires_context=True, confirmation=True)
# ID: b2553fd5-8aac-4bb2-af48-744aeebbb1c4
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
    console.print(
        f"[bold cyan]🚀 {mode} project:[/bold cyan] '{name}' (Profile: {profile})"
    )

    # The service handles the heavy lifting via ActionExecutor
    await create_new_project(
        context=core_context, name=name, profile=profile, write=write
    )
