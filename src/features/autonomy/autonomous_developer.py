# src/features/autonomy/autonomous_developer.py

"""
Provides a dedicated, reusable service for orchestrating the full autonomous
development cycle, from goal to implemented code.

UPGRADED (Phase 2): Now uses ContextService for graph-aware context.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from shared.context import CoreContext
from shared.infrastructure.database.models import Task
from shared.logger import getLogger
from shared.models import PlanExecutionError
from will.agents.execution_agent import _ExecutionAgent
from will.agents.planner_agent import PlannerAgent


logger = getLogger(__name__)


def _format_context_package_report(packet: dict[str, Any]) -> str:
    """
    Transforms a structured ContextPackage into a readable report for the Planner.
    """
    report = ["# Context Report (Graph-Aware)\n"]
    items = packet.get("context", [])
    if not items:
        report.append("- No existing context found. Proceeding as a greenfield task.")
    else:
        report.append(f"Found {len(items)} relevant items in the Knowledge Graph:\n")
        files = set()
        symbols = []
        for item in items:
            name = item.get("name", "unknown")
            path = item.get("path", "unknown")
            summary = item.get("summary", "")[:200]
            files.add(path)
            symbols.append(
                f"- **{name}** ({item.get('item_type')}) in `{path}`\n  _{summary}_"
            )
        report.append("## Relevant Files")
        for f in sorted(files):
            report.append(f"- `{f}`")
        report.append("\n## Relevant Symbols")
        report.extend(symbols)
    return "\n".join(report)


# ID: 3b38d8e4-fe6c-44c8-9503-f5d0b29fc14e
async def develop_from_goal(
    session: AsyncSession,
    context: CoreContext,
    goal: str,
    executor_agent: _ExecutionAgent,
    task_id: str | None = None,
    output_mode: str = "direct",
):
    """
    Runs the full, end-to-end autonomous development cycle for a given goal.

    Args:
        session: Database session (injected dependency)
        context: Core context with services
        goal: High-level development goal
        executor_agent: Agent to execute the plan
        task_id: Optional task ID for tracking
        output_mode: Output mode ('direct' or 'crate')
    """
    try:
        logger.info("🚀 Initiating autonomous development cycle for goal: '%s'", goal)
        logger.info("   -> Output mode: %s", output_mode)
        logger.info("   -> Building ContextPackage (Graph + Search)...")

        context_service = context.context_service
        task_spec = {
            "task_id": task_id or "dev_task",
            "task_type": "code.generate",
            "summary": goal,
            "scope": {"traversal_depth": 1, "roots": ["src/"]},
            "constraints": {"max_items": 30, "max_tokens": 50000},
        }
        packet = await context_service.build_for_task(task_spec, use_cache=False)
        context_report = _format_context_package_report(packet)
        logger.info(
            "   -> Context Report generated (%s items).", len(packet.get("context", []))
        )

        planner = PlannerAgent(context.cognitive_service)
        plan = await planner.create_execution_plan(goal, context_report)

        if not plan:
            raise PlanExecutionError(
                "PlannerAgent failed to create a valid execution plan."
            )

        execution_success = False
        execution_message = ""

        try:
            execution_success, execution_message = await executor_agent.execute_plan(
                high_level_goal=goal, plan=plan
            )
        except Exception as e:
            execution_message = f"Execution failed: {e!s}"
            logger.warning("Plan execution had issues: %s", e)

        if output_mode == "crate":
            logger.info("   -> Extracting generated files for crate packaging...")
            generated_files = {}

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

            for task in plan:
                if task.params.file_path and task.params.code:
                    generated_files[task.params.file_path] = task.params.code

            if not generated_files:
                if not execution_success:
                    raise PlanExecutionError(execution_message)
                raise PlanExecutionError("No generated files found to package.")

            logger.info("   -> Extracted %s files for crate", len(generated_files))

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

            if task_id:
                status = "completed" if execution_success else "review_required"
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

            return (True, result)

        if not execution_success:
            raise PlanExecutionError(execution_message)

        if task_id:
            async with session.begin():
                stmt = update(Task).where(Task.id == task_id).values(status="completed")
                await session.execute(stmt)

        return (execution_success, execution_message)

    except (PlanExecutionError, Exception) as e:
        error_message = f"Autonomous development cycle failed: {e}"
        logger.error(error_message, exc_info=True)

        if task_id:
            async with session.begin():
                stmt = (
                    update(Task)
                    .where(Task.id == task_id)
                    .values(status="failed", failure_reason=error_message)
                )
                await session.execute(stmt)

        return (False, error_message)
