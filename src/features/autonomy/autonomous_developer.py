# src/features/autonomy/autonomous_developer.py

"""
Provides a dedicated, reusable service for orchestrating the full autonomous
development cycle, from goal to implemented code.

UPGRADED (Phase 2): Now uses ContextService for graph-aware context.
"""

from __future__ import annotations

from typing import Any

from services.database.models import Task
from services.database.session_manager import get_session
from shared.context import CoreContext
from shared.logger import getLogger
from shared.models import PlanExecutionError
from sqlalchemy import update
from will.agents.execution_agent import _ExecutionAgent
from will.agents.planner_agent import PlannerAgent

# DEPRECATED: from will.agents.reconnaissance_agent import ReconnaissanceAgent

logger = getLogger(__name__)


def _format_context_package_report(packet: dict[str, Any]) -> str:
    """
    Transforms a structured ContextPackage into a readable report for the Planner.
    """
    report = ["# Context Report (Graph-Aware)\n"]

    # 1. Context Items
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
            summary = item.get("summary", "")[:200]  # Truncate summary

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

        # --- CONTEXT GATHERING (Phase 2 Upgrade) ---
        # Instead of simple search, we build a full ContextPackage
        logger.info("   -> Building ContextPackage (Graph + Search)...")

        # Ensure ContextService is ready
        context_service = context.context_service

        # Create a task specification for the ContextBuilder
        task_spec = {
            "task_id": task_id or "dev_task",
            # FIX: Use 'code.generate' to match DB constraint, not 'code.generation'
            "task_type": "code.generate",
            "summary": goal,
            # This enables graph traversal to find callers/callees
            "scope": {"traversal_depth": 1, "roots": ["src/"]},
            "constraints": {"max_items": 30, "max_tokens": 50000},
        }
        # Build the packet (Search + Graph)
        packet = await context_service.build_for_task(task_spec, use_cache=False)

        # Format for the Planner LLM
        context_report = _format_context_package_report(packet)
        logger.info(
            f"   -> Context Report generated ({len(packet.get('context', []))} items)."
        )

        # --- PLANNING ---
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

            # 2. Try extracting from the plan object (fallback)
            for task in plan:
                if task.params.file_path and task.params.code:
                    generated_files[task.params.file_path] = task.params.code

            if not generated_files:
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

            return (True, result)

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
