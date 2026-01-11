# src/body/cli/commands/run.py
# ID: body.cli.commands.run
"""
Provides functionality for the run module.
Refactored to use the Constitutional CLI Framework.

UPDATED (Phase 5): Removed _ExecutionAgent dependency.
Now uses develop_from_goal which internally uses the new UNIX-compliant pattern.
"""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv

from features.autonomy.autonomous_developer import develop_from_goal
from features.introspection.vectorization_service import run_vectorize
from shared.cli_utils import core_command
from shared.context import CoreContext
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)
run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)


@run_app.command("develop")
@core_command(dangerous=True)  # Requires write permission to create files
# ID: 62ba6795-9621-4f4f-a700-71b56bd85b87
async def develop_command(
    ctx: typer.Context,
    goal: str | None = typer.Argument(
        None,
        help="The high-level development goal for CORE to achieve.",
    ),
    from_file: Path | None = typer.Option(
        None,
        "--from-file",
        "-f",
        help="Read the goal from a file instead of the command line.",
    ),
    # CONSTITUTIONAL FIX: Add explicit write option for Typer discovery
    write: bool = typer.Option(
        False, "--write", help="Actually apply changes to the codebase (Dangerous)."
    ),
):
    """
    Runs the autonomous development cycle for a high-level goal.

    UPDATED: Now uses develop_from_goal with new UNIX-compliant orchestration.
    No need to build agents manually - all handled internally.
    """
    context: CoreContext = ctx.obj

    # Determine goal
    if not goal and not from_file:
        logger.error(
            "❌ You must provide a goal either as an argument or with --from-file."
        )
        raise typer.Exit(code=1)

    if from_file:
        goal_content = from_file.read_text(encoding="utf-8").strip()
    else:
        goal_content = goal.strip() if goal else ""

    # Load environment
    load_dotenv()

    # Check LLM enabled
    async with get_session() as session:
        from shared.infrastructure.config_service import ConfigService

        config = await ConfigService.create(session)
        llm_enabled = await config.get_bool("LLM_ENABLED", default=False)

    if not llm_enabled:
        logger.error("❌ The 'develop' command requires LLMs to be enabled.")
        raise typer.Exit(code=1)

    # Execute autonomous development
    # NOTE: develop_from_goal now builds all agents internally!
    # No need to pass executor_agent anymore!
    async with get_session() as session:
        success, message = await develop_from_goal(
            session=session,
            context=context,
            goal=goal_content,
            task_id=None,
            output_mode="direct",
        )

    if success:
        from rich.console import Console

        c = Console()
        c.print(f"\n[bold green]✅ Goal execution successful:[/bold green] {message}")
        c.print(
            "   -> Run 'git status' to see changes and 'core-admin submit changes' to integrate."
        )
    else:
        logger.error("Goal execution failed: %s", message)
        raise typer.Exit(code=1)


@run_app.command("vectorize")
@core_command(dangerous=True)
# ID: f8e9d0a1-b2c3-4d5e-6f7a-8b9c0d1e2f3a
async def vectorize_command(
    ctx: typer.Context,
    # CONSTITUTIONAL FIX: Added write option for consistency with @core_command
    write: bool = typer.Option(False, "--write", help="Commit vectors to Qdrant."),
    force: bool = typer.Option(
        False, help="Force re-vectorization of all capabilities."
    ),
):
    """
    Vectorize capabilities in the knowledge base for semantic search.
    """
    context: CoreContext = ctx.obj

    logger.info("🚀 Starting capability vectorization process...")

    async with get_session() as session:
        from shared.infrastructure.config_service import ConfigService

        config = await ConfigService.create(session)
        llm_enabled = await config.get_bool("LLM_ENABLED", default=False)

    if not llm_enabled:
        logger.error("❌ LLMs must be enabled to generate embeddings.")
        raise typer.Exit(code=1)

    try:
        # Note: run_vectorize takes dry_run, which is !write
        await run_vectorize(
            context=context, session=session, dry_run=not write, force=force
        )
    except Exception as e:
        logger.error("❌ Orchestration failed: %s", e, exc_info=True)
        raise typer.Exit(code=1)
