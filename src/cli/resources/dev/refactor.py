# src/cli/resources/dev/refactor.py
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

from cli.utils import core_command
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
# ID: df3bf750-e564-41cc-beb5-e6da5a97ebc1
async def dev_refactor_cmd(
    ctx: typer.Context,
    goal: str = typer.Argument(..., help="High-level refactoring goal or file path."),
    write: bool = typer.Option(
        False, "--write", help="Apply changes. Default is dry-run."
    ),
    workflow: str = typer.Option(
        "refactor_modularity",
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
    )

    context: CoreContext = ctx.obj
    load_dotenv()
    async with get_session() as session:
        config = await ConfigService.create(session)
        if not await config.get_bool("LLM_ENABLED", default=False):
            logger.info(
                "[red]❌ LLM_ENABLED is False. Enable LLMs in database settings to use autonomous development.[/red]"
            )
            raise typer.Exit(code=1)
    workflow_type = workflow
    mode = "WRITE" if write else "DRY-RUN"
    logger.info(
        "[bold cyan]🤖 CORE Autonomous Refactor[/bold cyan] ([yellow]%s[/yellow] / %s)",
        workflow_type,
        mode,
    )
    logger.info("[dim]Goal: %s[/dim]\n", goal)
    success, message = await develop_from_goal(
        context=context,
        goal=goal,
        workflow_type=workflow_type,
        write=write,
        task_id=None,
    )
    if success:
        logger.info("\n[bold green]✅ Success:[/bold green] %s", message)
    else:
        logger.info("\n[bold red]❌ Failed:[/bold red] %s", message)
        raise typer.Exit(code=1)
