# src/cli/commands/run.py
"""
Registers and implements the 'run' command group for executing complex,
multi-step processes and autonomous cycles.
"""
from __future__ import annotations

import asyncio
from pathlib import Path
from typing import Optional

import typer
from dotenv import load_dotenv

from core.agents.execution_agent import ExecutionAgent
from core.agents.plan_executor import PlanExecutor
from core.agents.planner_agent import PlannerAgent
from core.agents.reconnaissance_agent import ReconnaissanceAgent
from core.knowledge_service import KnowledgeService
from core.prompt_pipeline import PromptPipeline
from features.introspection.vectorization_service import run_vectorize
from shared.config import settings
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import PlanExecutionError

log = getLogger("core_admin.run")

run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)


# ID: 404982f6-59cd-40a3-862c-282c14225d3e
async def run_development_cycle(
    context: CoreContext, goal: str, auto_commit: bool = True
) -> tuple[bool, str]:
    """
    Runs the full development cycle for a given goal using explicit dependencies from the context.
    """
    try:
        log.info(f"🚀 Received new development goal: '{goal}'")

        # Get services from the context
        git_service = context.git_service
        cognitive_service = context.cognitive_service
        # --- THIS IS THE FIX ---
        auditor_context = context.auditor_context
        # --- END OF FIX ---
        file_handler = context.file_handler
        planner_config = context.planner_config

        await cognitive_service.initialize()

        # These are lightweight and can be created on-the-fly
        knowledge_service = KnowledgeService(repo_path=settings.REPO_PATH)
        prompt_pipeline = PromptPipeline(repo_path=settings.REPO_PATH)
        plan_executor = PlanExecutor(file_handler, git_service, planner_config)

        knowledge_graph = await knowledge_service.get_graph()

        recon_agent = ReconnaissanceAgent(knowledge_graph, cognitive_service)
        context_report = await recon_agent.generate_report(goal)

        planner = PlannerAgent(cognitive_service)
        plan = await planner.create_execution_plan(goal, context_report)

        executor = ExecutionAgent(
            cognitive_service, prompt_pipeline, plan_executor, auditor_context
        )

        if not plan:
            return False, "PlannerAgent failed to create a valid execution plan."

        success, message = await executor.execute_plan(high_level_goal=goal, plan=plan)

        if success and auto_commit:
            commit_goal = (goal[:72] + "...") if len(goal) > 75 else goal
            commit_message = f"feat(AI): execute plan for goal - {commit_goal}"
            git_service.commit(commit_message)
            log.info(f"   -> Committed changes with message: '{commit_message}'")
        return success, message
    except PlanExecutionError as e:
        return False, f"A critical error occurred during planning: {e}"
    except Exception as e:
        log.error(f"💥 An unexpected error occurred: {e}", exc_info=True)
        return False, f"An unexpected error occurred: {e}"


# ID: b6963057-2c08-4699-94ea-a7f74fe532ff
def develop(
    context: CoreContext,
    goal: Optional[str] = typer.Argument(
        None,
        help="The high-level development goal for CORE to achieve.",
        show_default=False,
    ),
    from_file: Optional[Path] = typer.Option(
        None,
        "--from-file",
        "-f",
        help="Path to a file containing the development goal.",
        exists=True,
        dir_okay=False,
        resolve_path=True,
        show_default=False,
    ),
):
    """Orchestrates the autonomous development process from a high-level goal."""
    if not goal and not from_file:
        log.error(
            "❌ You must provide a goal either as an argument or with --from-file."
        )
        raise typer.Exit(code=1)

    if from_file:
        goal_content = from_file.read_text(encoding="utf-8")
    else:
        goal_content = goal

    load_dotenv()
    if not settings.LLM_ENABLED:
        log.error("❌ The 'develop' command requires LLMs to be enabled.")
        raise typer.Exit(code=1)

    success, message = asyncio.run(run_development_cycle(context, goal_content))

    if success:
        typer.secho("\n✅ Goal achieved successfully.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"\n❌ Goal execution failed: {message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


# ID: f82043e9-6402-4cfd-8550-12b5feba09de
def vectorize_capabilities(
    context: CoreContext,
    dry_run: bool = typer.Option(
        True, "--dry-run/--write", help="Show changes without writing to Qdrant."
    ),
    force: bool = typer.Option(
        False, "--force", help="Force re-vectorization of all capabilities."
    ),
):
    """The CLI wrapper for the database-driven vectorization process."""
    log.info("🚀 Starting capability vectorization process...")
    if not settings.LLM_ENABLED:
        log.error("❌ LLMs must be enabled to generate embeddings.")
        raise typer.Exit(code=1)
    try:
        cognitive_service = context.cognitive_service
        asyncio.run(
            run_vectorize(
                cognitive_service=cognitive_service, dry_run=dry_run, force=force
            )
        )
    except Exception as e:
        log.error(f"❌ Orchestration failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


# ID: 1d2e3f4a-5b6c-7d8e-9f0a-1b2c3d4e5f6a
def register(app: typer.Typer, context: CoreContext):
    """Register the 'run' command group with the main CLI app."""

    @run_app.command("develop")
    # ID: d10d0d34-054c-4923-bda9-1264f6d85813
    def develop_command(
        goal: Optional[str] = typer.Argument(
            None,
            help="The high-level development goal for CORE to achieve.",
            show_default=False,
        ),
        from_file: Optional[Path] = typer.Option(
            None,
            "--from-file",
            "-f",
            help="Path to a file containing the development goal.",
            exists=True,
            dir_okay=False,
            resolve_path=True,
            show_default=False,
        ),
    ):
        """Orchestrates the autonomous development process from a high-level goal."""
        develop(context=context, goal=goal, from_file=from_file)

    @run_app.command("vectorize")
    # ID: 61b0c0e6-41ad-4050-bb23-54d39ef9e248
    def vectorize_command(
        dry_run: bool = typer.Option(
            True, "--dry-run/--write", help="Show changes without writing to Qdrant."
        ),
        force: bool = typer.Option(
            False, "--force", help="Force re-vectorization of all capabilities."
        ),
    ):
        """Scan capabilities from the DB, generate embeddings, and upsert to Qdrant."""
        vectorize_capabilities(context=context, dry_run=dry_run, force=force)

    app.add_typer(run_app, name="run")
