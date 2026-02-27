# src/cli/resources/dev/refactor.py
# ID: cli.resources.dev.refactor

"""
Autonomous refactoring command.

Wires the 'core-admin dev refactor' command to CORE's autonomous
development engine (develop_from_goal_v2). This is the operator's
entry point for letting CORE fix its own code.
"""

from __future__ import annotations

import typer
from dotenv import load_dotenv
from rich.console import Console

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.models.command_meta import CommandBehavior, CommandLayer, command_meta

from .hub import app


logger = getLogger(__name__)
console = Console()


@app.command("refactor")
@command_meta(
    canonical_name="dev.refactor",
    behavior=CommandBehavior.MUTATE,
    layer=CommandLayer.WILL,
    summary="Invoke CORE's autonomous agent loop to refactor code toward a goal.",
    dangerous=True,
)
@core_command(dangerous=True, requires_context=True)
# ID: dev-refactor-cmd-001
# ID: dab0f73f-6db6-41bf-bac4-e57747fb737f
async def dev_refactor_cmd(
    ctx: typer.Context,
    goal: str = typer.Argument(
        ...,
        help="High-level refactoring goal or file path.",
    ),
    write: bool = typer.Option(
        False, "--write", help="Apply changes. Default is dry-run."
    ),
    workflow: str = typer.Option(
        "auto",
        "--workflow",
        help="Workflow type: auto, refactor_modularity, coverage_remediation.",
    ),
) -> None:
    """
    Invoke CORE's autonomous agent loop on a refactoring goal.

    CORE will use its own sensory tools (search_vectors, lookup_symbol,
    read_file) to navigate the codebase and propose a fix — without
    being handed code directly.

    Examples:
      core-admin dev refactor "Fix logic.logging.standard_only violations"
      core-admin dev refactor src/shared/utils.py --write
      core-admin dev refactor "Improve modularity of executor.py" --write
    """
    from will.autonomy.autonomous_developer import (
        develop_from_goal,
        infer_workflow_type,
    )

    context: CoreContext = ctx.obj

    load_dotenv()

    # Pre-flight: LLM must be enabled
    async with get_session() as session:
        config = await ConfigService.create(session)
        if not await config.get_bool("LLM_ENABLED", default=False):
            console.print(
                "[red]❌ LLM_ENABLED is False. "
                "Enable LLMs in database settings to use autonomous development.[/red]"
            )
            raise typer.Exit(code=1)

    # Resolve workflow type
    workflow_type = infer_workflow_type(goal) if workflow == "auto" else workflow

    mode = "WRITE" if write else "DRY-RUN"
    console.print(
        f"[bold cyan]🤖 CORE Autonomous Refactor[/bold cyan] "
        f"([yellow]{workflow_type}[/yellow] / {mode})"
    )
    console.print(f"[dim]Goal: {goal}[/dim]\n")

    success, message = await develop_from_goal(
        context=context,
        goal=goal,
        workflow_type=workflow_type,
        write=write,
        task_id=None,
    )

    if success:
        console.print(f"\n[bold green]✅ Success:[/bold green] {message}")
    else:
        console.print(f"\n[bold red]❌ Failed:[/bold red] {message}")
        raise typer.Exit(code=1)
