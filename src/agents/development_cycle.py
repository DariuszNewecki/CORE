# src/agents/development_cycle.py
"""
Provides the primary autonomous development cycle function that orchestrates planning and execution for self-directed software development.
"""
from __future__ import annotations

from typing import Any, Dict, Tuple

from agents.execution_agent import ExecutionAgent
from agents.plan_executor import PlanExecutor
from agents.planner_agent import PlannerAgent
from agents.reconnaissance_agent import ReconnaissanceAgent
from core.cognitive_service import CognitiveService
from core.file_handler import FileHandler
from core.git_service import GitService
from core.knowledge_service import KnowledgeService
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
        log.info("   -> Initializing CORE services for development cycle...")
        cognitive_service = CognitiveService(settings.REPO_PATH)
        knowledge_service = KnowledgeService(settings.REPO_PATH)
        file_handler = FileHandler(str(settings.REPO_PATH))
        git_service = GitService(str(settings.REPO_PATH))
        prompt_pipeline = PromptPipeline(settings.REPO_PATH)
        agent_policy = load_config(
            settings.REPO_PATH / ".intent/policies/agent_behavior_policy.yaml"
        )
        context: Dict[str, Any] = {"policies": {"agent_behavior_policy": agent_policy}}

        recon_agent = ReconnaissanceAgent(knowledge_service.graph)
        surgical_context = recon_agent.generate_report(goal)
        context["surgical_context"] = surgical_context

        log.info("   -> Assembling autonomous agents...")

        # --- MODIFICATION START ---
        # PlannerAgent is now instantiated with the service itself.
        planner = PlannerAgent(
            cognitive_service=cognitive_service,
            prompt_pipeline=prompt_pipeline,
            context=context,
        )
        # --- MODIFICATION END ---

        plan_executor = PlanExecutor(
            file_handler=file_handler,
            git_service=git_service,
            config=planner.config,
        )
        execution_agent = ExecutionAgent(
            cognitive_service=cognitive_service,
            prompt_pipeline=prompt_pipeline,
            plan_executor=plan_executor,
        )

        log.info("🧠 PlannerAgent: Decomposing goal into a high-level plan...")
        plan = planner.create_execution_plan(goal)

        if not plan:
            return False, "PlannerAgent failed to create a valid execution plan."

        log.info("⚡ ExecutionAgent: Starting execution of the plan...")
        success, message = await execution_agent.execute_plan(goal, plan)

        return success, message

    except Exception as e:
        log.error(
            f"💥 An unexpected error occurred during the development cycle: {e}",
            exc_info=True,
        )
        return False, f"An unexpected error occurred: {str(e)}"
