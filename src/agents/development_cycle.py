# src/agents/development_cycle.py
"""
Intent: Provides a single, reusable function that encapsulates the entire
autonomous development cycle. This is the "heart" of CORE's self-development
capability, ensuring the process is consistent whether triggered by the CLI
or an API call. This adheres to the `dry_by_design` principle.
"""
from typing import Any, Dict, Tuple

from agents.execution_agent import ExecutionAgent
from agents.plan_executor import PlanExecutor
from agents.planner_agent import PlannerAgent
from core.cognitive_service import CognitiveService
from core.file_handler import FileHandler
from core.git_service import GitService
from core.prompt_pipeline import PromptPipeline
from shared.config import settings
from shared.config_loader import load_config
from shared.logger import getLogger

log = getLogger("development_cycle")


async def run_development_cycle(goal: str) -> Tuple[bool, str]:
    """
    Executes a full, autonomous development cycle from a high-level goal.
    """
    try:
        # Step 1: Instantiate services. The CognitiveService is now the source of LLM clients.
        log.info("   -> Initializing CORE services for development cycle...")
        cognitive_service = CognitiveService(settings.REPO_PATH)
        file_handler = FileHandler(str(settings.REPO_PATH))
        git_service = GitService(str(settings.REPO_PATH))
        prompt_pipeline = PromptPipeline(settings.REPO_PATH)

        # Load agent behavior policy from the constitution
        agent_policy = load_config(
            settings.REPO_PATH / ".intent/policies/agent_behavior_policy.yaml"
        )
        context: Dict[str, Any] = {"policies": {"agent_behavior_policy": agent_policy}}

        # Step 2: Assemble agents using clients provided by the CognitiveService.
        log.info("   -> Assembling autonomous agents...")
        planner = PlannerAgent(
            orchestrator_client=cognitive_service.get_client_for_role("Planner"),
            prompt_pipeline=prompt_pipeline,
            context=context,
        )

        planner_config = planner.config
        if not planner_config:
            return (
                False,
                "Could not load planner configuration from agent_behavior_policy.yaml",
            )

        plan_executor = PlanExecutor(
            file_handler=file_handler,
            git_service=git_service,
            config=planner_config,
        )
        execution_agent = ExecutionAgent(
            generator_client=cognitive_service.get_client_for_role("Coder"),
            prompt_pipeline=prompt_pipeline,
            plan_executor=plan_executor,
        )

        # Step 3: Create the execution plan
        log.info("🧠 PlannerAgent: Decomposing goal into a high-level plan...")
        plan = planner.create_execution_plan(goal)

        if not plan:
            return False, "PlannerAgent failed to create a valid execution plan."

        # Step 4: Execute the plan
        log.info("⚡ ExecutionAgent: Starting execution of the plan...")
        success, message = await execution_agent.execute_plan(goal, plan)

        return success, message

    except Exception as e:
        log.error(
            f"💥 An unexpected error occurred during the development cycle: {e}",
            exc_info=True,
        )
        return False, f"An unexpected error occurred: {str(e)}"