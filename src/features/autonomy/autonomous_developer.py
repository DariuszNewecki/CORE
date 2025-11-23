# src/features/autonomy/autonomous_developer.py

"""
Provides a dedicated, reusable service for orchestrating the full autonomous
development cycle, from goal to implemented code.
"""

from __future__ import annotations

from sqlalchemy import update

from services.database.models import Task
from services.database.session_manager import get_session
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import PlanExecutionError
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

    This function receives a pre-configured ExecutionAgent and orchestrates
    the complete development workflow from reconnaissance through code generation
    and validation.

    Args:
        context: CoreContext with all services
        goal: High-level goal description in natural language
        executor_agent: Pre-configured ExecutionAgent instance
        task_id: Optional task ID for database tracking
        output_mode: Output behavior mode:
            - "direct" (default): Apply changes immediately to filesystem
            - "crate": Return generated files for intent crate packaging

    Returns:
        Tuple of (success: bool, result: Any) where result is:
        - In "direct" mode: message string describing what was done
        - In "crate" mode: dict with structure:
          {
              "files": {relative_path: content},
              "context_tokens": int,
              "generation_tokens": int,
              "plan": list[ExecutionTask]
          }

    Raises:
        PlanExecutionError: If planning or execution fails
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

        success, message = await executor_agent.execute_plan(
            high_level_goal=goal, plan=plan
        )

        if not success:
            raise PlanExecutionError(f"Execution failed: {message}")

        # Handle crate mode: extract generated files instead of applying directly
        if output_mode == "crate":
            logger.info("   -> Extracting generated files for crate packaging...")

            # Extract files from the plan executor's context
            # The executor stores file content in its context during execution
            generated_files = {}

            # Get files from plan executor's file content cache
            if hasattr(executor_agent.executor, "context") and hasattr(
                executor_agent.executor.context, "file_content_cache"
            ):
                file_cache = executor_agent.executor.context.file_content_cache

                # Convert absolute paths to relative paths for crate
                for abs_path, content in file_cache.items():
                    # Convert to relative path from repo root
                    try:
                        from pathlib import Path

                        rel_path = Path(abs_path).relative_to(
                            context.git_service.repo_path
                        )
                        generated_files[str(rel_path)] = content
                    except ValueError:
                        # If path is already relative or not under repo, use as-is
                        generated_files[abs_path] = content

            # If no files in cache, extract from plan tasks
            if not generated_files:
                logger.warning("   -> No files in cache, extracting from plan tasks...")
                for task in plan:
                    if task.params.file_path and task.params.code:
                        generated_files[task.params.file_path] = task.params.code

            if not generated_files:
                raise PlanExecutionError(
                    "Crate mode enabled but no generated files found. "
                    "This may indicate the plan didn't generate any code."
                )

            logger.info(f"   -> Extracted {len(generated_files)} files for crate")

            result = {
                "files": generated_files,
                "context_tokens": 0,  # TODO: Track from agents in future
                "generation_tokens": 0,  # TODO: Track from agents in future
                "plan": [task.model_dump() for task in plan],
            }

            # Update task status if provided
            if task_id:
                async with get_session() as session:
                    async with session.begin():
                        stmt = (
                            update(Task)
                            .where(Task.id == task_id)
                            .values(status="completed")
                        )
                        await session.execute(stmt)

            return (True, result)

        # Direct mode: normal flow (existing behavior)
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
