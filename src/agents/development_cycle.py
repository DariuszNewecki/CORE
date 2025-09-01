# src/agents/development_cycle.py
"""
Orchestrates the autonomous development cycle, including reconnaissance, planning, and execution.
"""

from __future__ import annotations

from agents.execution_agent import ExecutionAgent
from agents.models import PlannerConfig
from agents.plan_executor import PlanExecutor
from agents.planner_agent import PlannerAgent
from agents.reconnaissance_agent import ReconnaissanceAgent
from core.cognitive_service import CognitiveService
from core.file_handler import FileHandler
from core.git_service import GitService
from core.prompt_pipeline import PromptPipeline
from shared.logger import getLogger
from shared.path_utils import get_repo_root

log = getLogger(__name__)


# CAPABILITY: agent.plan.error
class PlanExecutionError(Exception):
    """Custom exception for errors during the planning or execution phase."""

    pass


# CAPABILITY: agent.development_cycle.execute
async def run_development_cycle(
    goal: str, auto_commit: bool = True
) -> tuple[bool, str]:
    """
    Runs the full development cycle for a given goal.

    Args:
        goal: The high-level goal to be achieved.
        auto_commit: Whether to automatically commit the changes on success.

    Returns:
        A tuple containing (success: bool, message: str).
    """
    try:
        log.info(f"🚀 Received new development goal: '{goal}'")
        log.info("   -> Initializing CORE services for development cycle...")

        repo_path = get_repo_root()
        git_service = GitService(repo_path=str(repo_path))
        cognitive_service = CognitiveService(repo_path=repo_path)
        file_handler = FileHandler(repo_path=str(repo_path))
        prompt_pipeline = PromptPipeline(repo_path=repo_path)
        planner_config = PlannerConfig()
        plan_executor = PlanExecutor(
            file_handler=file_handler,
            git_service=git_service,
            config=planner_config,
        )

        log.info("🔬 Conducting reconnaissance for goal: '%s'", goal)
        knowledge_graph = {"symbols": {}}  # Placeholder for now
        recon_agent = ReconnaissanceAgent(knowledge_graph)
        context = recon_agent.generate_report(goal)
        log.info("   -> Generated Surgical Context Report:\n" + context)

        log.info("   -> Assembling autonomous agents...")
        planner = PlannerAgent(cognitive_service=cognitive_service)
        executor = ExecutionAgent(
            cognitive_service=cognitive_service,
            prompt_pipeline=prompt_pipeline,
            plan_executor=plan_executor,
        )

        log.info("🧠 PlannerAgent: Decomposing goal into a high-level plan...")
        plan = planner.create_execution_plan(goal)

        if not plan:
            return False, "PlannerAgent failed to create a valid execution plan."

        # Execute the plan (async)
        success, message = await executor.execute_plan(high_level_goal=goal, plan=plan)

        if success and auto_commit:
            log.info("✅ Plan executed successfully. Committing changes...")
            commit_message = f"feat(AI): execute plan for goal - {goal}"
            # No need to stage here; GitService.commit() auto-stages
            git_service.commit(commit_message)
            log.info(f"   -> Committed changes with message: '{commit_message}'")

        return success, message

    except PlanExecutionError as e:
        log.error(f"💥 A critical error occurred during the planning phase: {e}")
        return False, f"A critical error occurred during planning: {e}"
    except Exception as e:
        log.error(
            f"💥 An unexpected error occurred during the development cycle: {e}",
            exc_info=True,
        )
        return False, f"An unexpected error occurred: {e}"
