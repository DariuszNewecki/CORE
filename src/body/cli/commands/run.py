# src/body/cli/commands/run.py
"""
Provides functionality for the run module.
Refactored to use the Constitutional CLI Framework.
"""

from __future__ import annotations

from pathlib import Path

import typer
from dotenv import load_dotenv

from features.autonomy.autonomous_developer import develop_from_goal
from features.introspection.vectorization_service import run_vectorize
from shared.cli_utils import core_command
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


@run_app.command("develop")
@core_command(dangerous=True)  # Requires write permission to create files
# ID: 62ba6795-9621-4f4f-a700-71b56bd85b87
async def develop_command(
    ctx: typer.Context,
    goal: str | None = typer.Argument(
        None,
        help="The high-level development goal for CORE to achieve.",
        show_default=False,
    ),
    from_file: Path | None = typer.Option(
        None,
        "--from-file",
        "-f",
        help="Path to a file containing the development goal.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
        show_default=False,
    ),
) -> None:
    """Orchestrates the autonomous development process from a high-level goal."""
    core_context: CoreContext = ctx.obj
    await _develop(context=core_context, goal=goal, from_file=from_file)


@run_app.command("vectorize")
@core_command(dangerous=True)  # Requires write permission to update Qdrant
# ID: fe1e4f7b-44a5-429f-8549-bd97760b3997
async def vectorize_command(
    ctx: typer.Context,
    write: bool = typer.Option(False, "--write", help="Persist changes to Qdrant."),
    force: bool = typer.Option(
        False, "--force", help="Force re-vectorization of all capabilities."
    ),
) -> None:
    """Scan capabilities from the DB, generate embeddings, and upsert to Qdrant."""
    core_context: CoreContext = ctx.obj
    # Manual JIT injection logic removed - handled by @core_command
    await run_vectorize(context=core_context, dry_run=not write, force=force)


# Logic helper - kept for isolation
async def _develop(
    context: CoreContext, goal: str | None = None, from_file: Path | None = None
):
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

    # Simplified config check - context already has what we need ideally,
    # but keeping logic similar to original for now
    from services.config_service import ConfigService
    from services.database.session_manager import get_session

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
        # Using simple prints here as it's not returning an ActionResult yet
        from rich.console import Console

        c = Console()
        c.console.print(
            f"\n[bold green]✅ Goal execution successful:[/bold green] {message}"
        )
        c.console.print(
            "   -> Run 'git status' to see changes and 'core-admin submit changes' to integrate."
        )
    else:
        logger.error("Goal execution failed: %s", message)
        raise typer.Exit(code=1)
