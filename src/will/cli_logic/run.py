# src/will/cli_logic/run.py
# ID: will.cli_logic.run
"""
Provides functionality for the run module.

UPDATED (Phase 5): Removed _ExecutionAgent dependency.
Now uses develop_from_goal which internally uses the new UNIX-compliant pattern.
"""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv

from features.autonomy.autonomous_developer import develop_from_goal
from features.introspection.vectorization_service import run_vectorize
from shared.context import CoreContext
from shared.infrastructure.config_service import ConfigService
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)
run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)


async def _develop(
    context: CoreContext, goal: str | None = None, from_file: Path | None = None
):
    """
    Orchestrates the autonomous development process from a high-level goal.

    UPDATED: Simplified! No need to build agents manually.
    develop_from_goal handles all orchestration internally.
    """
    if not goal and not from_file:
        logger.error(
            "❌ You must provide a goal either as an argument or with --from-file."
        )
        raise typer.Exit(code=1)

    if from_file:
        goal_content = from_file.read_text(encoding="utf-8").strip()
    else:
        goal_content = goal.strip() if goal else ""

    load_dotenv()

    async with get_session() as session:
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


async def _vectorize_capabilities(
    context: CoreContext, dry_run: bool = True, force: bool = False
):
    """The CLI wrapper for the database-driven vectorization process."""
    logger.info("🚀 Starting capability vectorization process...")

    async with get_session() as session:
        config = await ConfigService.create(session)
        llm_enabled = await config.get_bool("LLM_ENABLED", default=False)

    if not llm_enabled:
        logger.error("❌ LLMs must be enabled to generate embeddings.")
        raise typer.Exit(code=1)

    try:
        await run_vectorize(context=context, dry_run=dry_run, force=force)
    except Exception as e:
        logger.error("❌ Orchestration failed: %s", e, exc_info=True)
        raise typer.Exit(code=1)
