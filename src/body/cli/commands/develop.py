# src/body/cli/commands/develop.py
# ID: body.cli.commands.develop
"""
Unified interface for AI-native development with constitutional governance.

This is the primary home for the 'develop' command group.
It leverages the 'develop_from_goal' service to initiate autonomous cycles.
"""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from features.autonomy.autonomous_developer import develop_from_goal
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)
console = Console()

develop_app = typer.Typer(
    help="AI-native development with constitutional governance", no_args_is_help=True
)


@develop_app.command("refactor")
@core_command(dangerous=True)
# ID: d18c7126-5bb2-4feb-8810-031f5ffdba2d
async def refactor_command(
    ctx: typer.Context,
    goal: str | None = typer.Argument(
        None,
        help="The high-level goal for CORE to achieve (e.g. 'Refactor UserService').",
    ),
    from_file: Path | None = typer.Option(
        None,
        "--from-file",
        "-f",
        help="Read the goal from a file.",
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually apply changes to the codebase."
    ),
):
    """
    Initiates an autonomous development/refactoring cycle.

    Example:
      core-admin develop refactor "Improve modularity of shared/utils.py" --write
    """
    context: CoreContext = ctx.obj

    # 1. Determine the goal
    if not goal and not from_file:
        logger.error(
            "❌ You must provide a goal either as an argument or with --from-file."
        )
        raise typer.Exit(code=1)

    goal_content = (
        from_file.read_text(encoding="utf-8").strip() if from_file else goal.strip()
    )

    # 2. Pre-flight checks
    load_dotenv()
    async with get_session() as session:
        from shared.infrastructure.config_service import ConfigService

        config = await ConfigService.create(session)
        if not await config.get_bool("LLM_ENABLED", default=False):
            logger.error(
                "❌ The 'develop' command requires LLMs to be enabled in settings."
            )
            raise typer.Exit(code=1)

    # 3. Execute via the high-level Autonomous Developer service
    logger.info("🚀 Starting autonomous refactor for: %s", goal_content)

    async with get_session() as session:
        success, message = await develop_from_goal(
            session=session,
            context=context,
            goal=goal_content,
            task_id=None,
            output_mode="direct",
            write=write,  # Passing the human intent flag
        )

    if success:
        console.print(f"\n[bold green]✅ Success:[/bold green] {message}")
    else:
        logger.error("Goal execution failed: %s", message)
        raise typer.Exit(code=1)


@develop_app.command("info")
# ID: d2c8a1d6-f58a-4278-be58-487c317ba878
def info():
    """Show information about the autonomous development system."""
    console.print(
        Panel.fit(
            "[bold cyan]CORE Autonomous Development[/bold cyan]\n\n"
            "This command group uses the A3 (Planning-Specification-Execution) loop\n"
            "to perform complex code modifications autonomously.\n\n"
            'Usage: [yellow]core-admin develop refactor "your goal"[/yellow]',
            border_style="cyan",
        )
    )
