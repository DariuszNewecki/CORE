# src/will/cli_logic/run.py

"""Provides functionality for the run module."""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv

from features.autonomy.autonomous_developer import develop_from_goal
from features.introspection.vectorization_service import run_vectorize

# FIX: Import Class and Session Manager, not the helper function
from services.config_service import ConfigService
from services.database.session_manager import get_session
from shared.context import CoreContext
from shared.logger import getLogger
from will.agents.coder_agent import CoderAgent
from will.agents.execution_agent import _ExecutionAgent
from will.agents.plan_executor import PlanExecutor
from will.orchestration.prompt_pipeline import PromptPipeline


logger = getLogger(__name__)
run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)


# ID: ca0e111a-4d71-42db-bbc7-540e6ea756a0
async def _develop(
    context: CoreContext, goal: str | None = None, from_file: Path | None = None
):
    """Orchestrates the autonomous development process from a high-level goal."""
    if not goal and (not from_file):
        logger.error(
            "❌ You must provide a goal either as an argument or with --from-file."
        )
        raise typer.Exit(code=1)
    if from_file:
        goal_content = from_file.read_text(encoding="utf-8").strip()
    else:
        goal_content = goal.strip() if goal else ""
    load_dotenv()

    # FIX: Instantiate ConfigService with a session
    async with get_session() as session:
        config = await ConfigService.create(session)
        llm_enabled = await config.get_bool("LLM_ENABLED", default=False)

    if not llm_enabled:
        logger.error("❌ The 'develop' command requires LLMs to be enabled.")
        raise typer.Exit(code=1)
    prompt_pipeline = PromptPipeline(context.git_service.repo_path)
    plan_executor = PlanExecutor(
        context.file_handler, context.git_service, context.planner_config
    )
    coder_agent = CoderAgent(
        cognitive_service=context.cognitive_service,
        prompt_pipeline=prompt_pipeline,
        auditor_context=context.auditor_context,
    )
    executor_agent = _ExecutionAgent(
        coder_agent=coder_agent,
        plan_executor=plan_executor,
        auditor_context=context.auditor_context,
    )
    success, message = await develop_from_goal(context, goal_content, executor_agent)
    if success:
        typer.secho(f"\n✅ Goal execution successful: {message}", fg=typer.colors.GREEN)
        typer.secho(
            "   -> Run 'git status' to see the changes and 'core-admin submit changes' to integrate them.",
            bold=True,
        )
    else:
        typer.secho(f"\n❌ Goal execution failed: {message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


# ID: 0c28ad61-1da0-4764-9dbd-ca38ffd90efa
async def _vectorize_capabilities(
    context: CoreContext, dry_run: bool = True, force: bool = False
):
    """The CLI wrapper for the database-driven vectorization process."""
    logger.info("🚀 Starting capability vectorization process...")

    # FIX: Instantiate ConfigService with a session
    async with get_session() as session:
        config = await ConfigService.create(session)
        llm_enabled = await config.get_bool("LLM_ENABLED", default=False)

    if not llm_enabled:
        logger.error("❌ LLMs must be enabled to generate embeddings.")
        raise typer.Exit(code=1)
    try:
        await run_vectorize(context=context, dry_run=dry_run, force=force)
    except Exception as e:
        logger.error(f"❌ Orchestration failed: {e}", exc_info=True)
        raise typer.Exit(code=1)
