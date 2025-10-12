# src/features/autonomy/autonomous_developer.py
"""
Provides a dedicated, reusable service for orchestrating the full autonomous
development cycle, from goal to implemented code.
"""

from __future__ import annotations

from core.agents.coder_agent import CoderAgent
from core.agents.execution_agent import ExecutionAgent
from core.agents.plan_executor import PlanExecutor
from core.agents.planner_agent import PlannerAgent
from core.agents.reconnaissance_agent import ReconnaissanceAgent
from core.prompt_pipeline import PromptPipeline
from services.database.models import Task
from services.database.session_manager import get_session
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import PlanExecutionError
from sqlalchemy import update

log = getLogger("autonomous_developer")


# ID: 7a8b9c0d-1e2f-3a4b-5c6d-7e8f9a0b
# ID: f40722fc-751e-4643-81d7-99509b5baa91
async def develop_from_goal(
    context: CoreContext, goal: str, task_id: str | None = None
):
    """
    Runs the full, end-to-end autonomous development cycle for a given goal.
    This is the single source of truth for the A2 development loop.
    Now includes robust error handling and database status updates.
    """
    try:
        log.info(f"🚀 Initiating autonomous development cycle for goal: '{goal}'")

        # 1. Reconnaissance
        recon_agent = ReconnaissanceAgent(
            await context.knowledge_service.get_graph(), context.cognitive_service
        )
        context_report = await recon_agent.generate_report(goal)

        # 2. Planning
        planner = PlannerAgent(context.cognitive_service)
        plan = await planner.create_execution_plan(goal, context_report)
        if not plan:
            raise PlanExecutionError(
                "PlannerAgent failed to create a valid execution plan."
            )

        # 3. Execution
        prompt_pipeline = PromptPipeline(context.git_service.repo_path)
        plan_executor = PlanExecutor(
            context.file_handler, context.git_service, context.planner_config
        )
        coder_agent = CoderAgent(
            cognitive_service=context.cognitive_service,
            prompt_pipeline=prompt_pipeline,
            auditor_context=context.auditor_context,
        )
        executor_agent = ExecutionAgent(
            coder_agent=coder_agent,
            plan_executor=plan_executor,
            auditor_context=context.auditor_context,
        )

        success, message = await executor_agent.execute_plan(
            high_level_goal=goal, plan=plan
        )

        if not success:
            raise PlanExecutionError(f"Execution failed: {message}")

        if task_id:
            async with get_session() as session:
                async with session.begin():
                    stmt = (
                        update(Task)
                        .where(Task.id == task_id)
                        .values(status="completed")
                    )
                    await session.execute(stmt)

    except (PlanExecutionError, Exception) as e:
        error_message = f"Autonomous development cycle failed: {e}"
        log.error(error_message, exc_info=True)
        if task_id:
            async with get_session() as session:
                async with session.begin():
                    stmt = (
                        update(Task)
                        .where(Task.id == task_id)
                        .values(status="failed", failure_reason=error_message)
                    )
                    await session.execute(stmt)
