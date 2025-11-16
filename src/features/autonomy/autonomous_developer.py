# src/features/autonomy/autonomous_developer.py

"""
Provides a dedicated, reusable service for orchestrating the full autonomous
development cycle, from goal to implemented code.
"""

from __future__ import annotations

from services.database.models import Task
from services.database.session_manager import get_session
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import PlanExecutionError
from sqlalchemy import update
from will.agents.execution_agent import ExecutionAgent
from will.agents.planner_agent import PlannerAgent
from will.agents.reconnaissance_agent import ReconnaissanceAgent

logger = getLogger(__name__)


# ID: a37be1f9-d912-487f-bfde-1efddb155017
async def develop_from_goal(
    context: CoreContext,
    goal: str,
    executor_agent: ExecutionAgent,
    task_id: str | None = None,
):
    """
    Runs the full, end-to-end autonomous development cycle for a given goal.
    This function now receives a pre-configured ExecutionAgent.
    """
    try:
        logger.info(f"🚀 Initiating autonomous development cycle for goal: '{goal}'")
        goal_lower = goal.lower()
        if "create" in goal_lower and (
            "new file" in goal_lower or "new function" in goal_lower
        ):
            logger.info(
                "   -> Intent classified as 'CREATE_FILE'. Using specialized planner."
            )
            context_report = "# Reconnaissance Report\n\n- No relevant files found. Proceeding with file creation."
            planner = PlannerAgent(context.cognitive_service)
        else:
            logger.info(
                "   -> Intent classified as 'GENERAL'. Using standard reconnaissance and planning."
            )
            recon_agent = ReconnaissanceAgent(
                await context.knowledge_service.get_graph(), context.cognitive_service
            )
            context_report = await recon_agent.generate_report(goal)
            planner = PlannerAgent(context.cognitive_service)
        plan = await planner.create_execution_plan(goal, context_report)
        if not plan:
            raise PlanExecutionError(
                "PlannerAgent failed to create a valid execution plan."
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
        return (success, message)
    except (PlanExecutionError, Exception) as e:
        error_message = f"Autonomous development cycle failed: {e}"
        logger.error(error_message, exc_info=True)
        if task_id:
            async with get_session() as session:
                async with session.begin():
                    stmt = (
                        update(Task)
                        .where(Task.id == task_id)
                        .values(status="failed", failure_reason=error_message)
                    )
                    await session.execute(stmt)
        return (False, error_message)
