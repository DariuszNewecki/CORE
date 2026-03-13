# src/cli/commands/develop.py
"""
Unified interface for AI-native development.
UPDATED: Import now points to will.autonomy (Wave 1).
"""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv
from rich.console import Console
from rich.panel import Panel

from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from will.autonomy.autonomous_developer import develop_from_goal


logger = getLogger(__name__)
console = Console()
develop_app = typer.Typer(
    help="AI-native development with constitutional governance", no_args_is_help=True
)


@develop_app.command("refactor")
@core_command(dangerous=True)
# ID: 44c3e345-cc9a-4a81-a207-0ea84b69ff37
async def refactor_command(
    ctx: typer.Context,
    goal: str | None = typer.Argument(
        None,
        help="File path or high-level refactoring goal (e.g. 'src/utils.py' or 'Improve modularity of UserService').",
    ),
    from_file: Path | None = typer.Option(
        None, "--from-file", "-f", help="Read the goal from a file."
    ),
    write: bool = typer.Option(
        False, "--write", help="Actually apply changes to the codebase."
    ),
):
    """
    Initiates an autonomous refactoring cycle.

    The command intelligently formats goals for INTERPRET phase:
    - If goal looks like a file path: "refactor {path} for better modularity"
    - If goal is natural language: passes as-is

    Examples:
      core-admin develop refactor src/shared/utils.py --write
      core-admin develop refactor "Improve modularity of UserService" --write
    """
    context: CoreContext = ctx.obj
    if not goal and (not from_file):
        logger.error(
            "❌ You must provide a goal either as an argument or with --from-file."
        )
        raise typer.Exit(code=1)
    raw_goal = (
        from_file.read_text(encoding="utf-8").strip() if from_file else goal.strip()
    )
    goal_content = _format_refactor_goal(raw_goal)
    if goal_content != raw_goal:
        logger.info("🔍 Formatted goal for INTERPRET phase: %s", goal_content)
    load_dotenv()
    async with get_session() as session:
        from shared.infrastructure.config_service import ConfigService

        config = await ConfigService.create(session)
        if not await config.get_bool("LLM_ENABLED", default=False):
            logger.error(
                "❌ The 'develop' command requires LLMs to be enabled in settings."
            )
            raise typer.Exit(code=1)
    logger.info("🚀 Starting autonomous refactor for: %s", goal_content)
    async with get_session() as session:
        success, message = await develop_from_goal(
            context=context,
            goal=goal_content,
            workflow_type="refactor_modularity",
            write=write,
            task_id=None,
        )
    if success:
        logger.info("\n[bold green]✅ Success:[/bold green] %s", message)
    else:
        logger.error("Goal execution failed: %s", message)
        raise typer.Exit(code=1)


def _format_refactor_goal(raw_goal: str) -> str:
    """
    Format raw goal into INTERPRET-friendly refactoring goal.

    Rules:
    - If goal looks like a file path → add refactoring context
    - If goal already contains refactoring keywords → pass as-is
    - If goal is natural language → pass as-is

    Args:
        raw_goal: Raw user input

    Returns:
        Formatted goal with refactoring context

    Examples:
        "src/utils.py" → "refactor src/utils.py for better modularity"
        "Improve UserService" → "Improve UserService" (unchanged)
        "refactor the auth module" → "refactor the auth module" (unchanged)
    """
    refactor_keywords = [
        "refactor",
        "modularity",
        "split",
        "extract",
        "improve",
        "clarity",
    ]
    if any(keyword in raw_goal.lower() for keyword in refactor_keywords):
        return raw_goal
    if "/" in raw_goal or raw_goal.endswith(".py"):
        return f"refactor {raw_goal} for better modularity"
    return raw_goal


@develop_app.command("info")
# ID: 7964aa47-e138-4519-bdf3-e788b388e426
def info():
    """Show information about the autonomous development system."""
    logger.info(
        Panel.fit(
            '[bold cyan]CORE Autonomous Development[/bold cyan]\n\nThis command group uses the A3 (Planning-Specification-Execution) loop\nto perform complex code modifications autonomously.\n\nUsage: [yellow]core-admin develop refactor "your goal"[/yellow]\n\n[bold]Smart Goal Formatting:[/bold]\n• File paths are auto-formatted with refactoring context\n• Natural language goals pass through unchanged\n\nExamples:\n  core-admin develop refactor src/utils.py --write\n  core-admin develop refactor "Improve clarity of AuthService" --write',
            border_style="cyan",
        )
    )
