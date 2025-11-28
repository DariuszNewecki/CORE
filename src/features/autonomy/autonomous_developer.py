# src/features/autonomy/autonomous_developer.py

"""
Provides a dedicated, reusable service for orchestrating the full autonomous
development cycle, from goal to implemented code.

UPDATED: Now creates crates even on validation failure for human review.
"""

from __future__ import annotations

from services.database.models import Task
from services.database.session_manager import get_session
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import PlanExecutionError
from sqlalchemy import update
from will.agents.execution_agent import _ExecutionAgent
from will.agents.planner_agent import PlannerAgent
from will.agents.reconnaissance_agent import ReconnaissanceAgent

logger = getLogger(__name__)


# ID: a37be1f9-d912-487f-bfde-1efddb155017
async def develop_from_goal(
    context: CoreContext,
    goal: str,
    executor_agent: _ExecutionAgent,
    task_id: str | None = None,
    output_mode: str = "direct",
):
    """
    Runs the full, end-to-end autonomous development cycle for a given goal.
    """
    try:
        logger.info(f"🚀 Initiating autonomous development cycle for goal: '{goal}'")
        logger.info(f"   -> Output mode: {output_mode}")

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

        # Execute the plan
        execution_success = False
        execution_message = ""

        try:
            execution_success, execution_message = await executor_agent.execute_plan(
                high_level_goal=goal, plan=plan
            )
        except Exception as e:
            execution_message = f"Execution failed: {str(e)}"
            logger.warning(f"Plan execution had issues: {e}")
            # Continue to crate creation to salvage any generated code

        # Handle crate mode: extract generated files
        if output_mode == "crate":
            logger.info("   -> Extracting generated files for crate packaging...")

            generated_files = {}

            # 1. Try extracting from executor context (if successful run)
            if hasattr(executor_agent.executor, "context") and hasattr(
                executor_agent.executor.context, "file_content_cache"
            ):
                file_cache = executor_agent.executor.context.file_content_cache
                for abs_path, content in file_cache.items():
                    try:
                        from pathlib import Path

                        rel_path = Path(abs_path).relative_to(
                            context.git_service.repo_path
                        )
                        generated_files[str(rel_path)] = content
                    except ValueError:
                        generated_files[abs_path] = content

            # 2. Try extracting from the plan object (if partial run or cache missed)
            # This works because plan tasks are modified in-place with generated code
            for task in plan:
                if task.params.file_path and task.params.code:
                    generated_files[task.params.file_path] = task.params.code

            if not generated_files:
                # Only hard fail if we have absolutely nothing to show
                if not execution_success:
                    raise PlanExecutionError(execution_message)
                raise PlanExecutionError("No generated files found to package.")

            logger.info(f"   -> Extracted {len(generated_files)} files for crate")

            result = {
                "files": generated_files,
                "context_tokens": 0,
                "generation_tokens": 0,
                "plan": [task.model_dump() for task in plan],
                "validation_passed": execution_success,
                "notes": (
                    execution_message
                    if not execution_success
                    else "Automatically generated."
                ),
            }

            # Update task status
            if task_id:
                status = "completed" if execution_success else "review_required"
                async with get_session() as session:
                    async with session.begin():
                        stmt = (
                            update(Task)
                            .where(Task.id == task_id)
                            .values(
                                status=status,
                                failure_reason=(
                                    execution_message if not execution_success else None
                                ),
                            )
                        )
                        await session.execute(stmt)

            return (True, result)  # Return True so CLI proceeds

        # Direct mode logic (unchanged)
        if not execution_success:
            raise PlanExecutionError(execution_message)

        if task_id:
            async with get_session() as session:
                async with session.begin():
                    stmt = (
                        update(Task)
                        .where(Task.id == task_id)
                        .values(status="completed")
                    )
                    await session.execute(stmt)

        return (execution_success, execution_message)

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
