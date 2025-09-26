# src/cli/commands/run.py
"""
Registers and implements the 'run' command group for executing complex,
multi-step processes and autonomous cycles.
"""
from __future__ import annotations

import asyncio

import typer
from dotenv import load_dotenv

from core.agents.execution_agent import ExecutionAgent
from core.agents.plan_executor import PlanExecutor
from core.agents.planner_agent import PlannerAgent
from core.agents.reconnaissance_agent import ReconnaissanceAgent
from core.cognitive_service import CognitiveService
from core.file_handler import FileHandler
from core.git_service import GitService
from core.knowledge_service import KnowledgeService
from core.prompt_pipeline import PromptPipeline
from features.governance.audit_context import AuditorContext
from features.introspection.vectorization_service import run_vectorize
from shared.config import settings
from shared.logger import getLogger
from shared.models import PlanExecutionError, PlannerConfig
from shared.path_utils import get_repo_root

log = getLogger("core_admin.run")

run_app = typer.Typer(
    help="Commands for executing complex processes and autonomous cycles."
)


# ID: 404982f6-59cd-40a3-862c-282c14225d3e
async def run_development_cycle(
    goal: str, auto_commit: bool = True
) -> tuple[bool, str]:
    """
    Runs the full development cycle for a given goal.
    """
    try:
        log.info(f"🚀 Received new development goal: '{goal}'")
        repo_path = get_repo_root()

        auditor_context = AuditorContext(repo_path)
        git_service = GitService(repo_path=str(repo_path))
        cognitive_service = CognitiveService(repo_path=repo_path)
        knowledge_service = KnowledgeService(repo_path=repo_path)
        file_handler = FileHandler(repo_path=str(repo_path))
        prompt_pipeline = PromptPipeline(repo_path=repo_path)
        planner_config = PlannerConfig()
        plan_executor = PlanExecutor(file_handler, git_service, planner_config)

        knowledge_graph = await knowledge_service.get_graph()

        # --- THIS IS THE FIX ---
        # The Recon Agent now requires the cognitive_service to do its own search
        recon_agent = ReconnaissanceAgent(knowledge_graph, cognitive_service)
        context_report = await recon_agent.generate_report(goal)

        planner = PlannerAgent(cognitive_service)
        # The planner now requires the report to generate an informed plan
        plan = await planner.create_execution_plan(goal, context_report)
        # --- END OF FIX ---

        executor = ExecutionAgent(
            cognitive_service, prompt_pipeline, plan_executor, auditor_context
        )

        if not plan:
            return False, "PlannerAgent failed to create a valid execution plan."

        success, message = await executor.execute_plan(
            high_level_goal=goal, plan=plan, is_micro_proposal=False
        )

        if success and auto_commit:
            commit_message = f"feat(AI): execute plan for goal - {goal}"
            git_service.commit(commit_message)
            log.info(f"   -> Committed changes with message: '{commit_message}'")
        return success, message
    except PlanExecutionError as e:
        return False, f"A critical error occurred during planning: {e}"
    except Exception as e:
        log.error(f"💥 An unexpected error occurred: {e}", exc_info=True)
        return False, f"An unexpected error occurred: {e}"


@run_app.command(
    "develop",
    help="Orchestrates the autonomous development process from a high-level goal.",
)
# ID: b6963057-2c08-4699-94ea-a7f74fe532ff
def develop(
    goal: str = typer.Argument(
        ..., help="The high-level development goal for CORE to achieve."
    )
):
    load_dotenv()
    if not settings.LLM_ENABLED:
        log.error("❌ The 'develop' command requires LLMs to be enabled.")
        raise typer.Exit(code=1)
    success, message = asyncio.run(run_development_cycle(goal))
    if success:
        typer.secho("\n✅ Goal achieved successfully.", fg=typer.colors.GREEN)
    else:
        typer.secho(f"\n❌ Goal execution failed: {message}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


@run_app.command(
    "vectorize",
    help="Scan capabilities from the DB, generate embeddings, and upsert to Qdrant.",
)
# ID: f82043e9-6402-4cfd-8550-12b5feba09de
def vectorize_capabilities(
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
        asyncio.run(run_vectorize(dry_run=dry_run, force=force))
    except Exception as e:
        log.error(f"❌ Orchestration failed: {e}", exc_info=True)
        raise typer.Exit(code=1)


# ID: ec7405ee-fb7c-424c-8d41-239a77a7a24d
def register(app: typer.Typer):
    """Register the 'run' command group with the main CLI app."""
    app.add_typer(run_app, name="run")
