# src/features/autonomy/autonomous_developer.py
# ID: features.autonomy.autonomous_developer
"""
Provides a dedicated, reusable service for orchestrating the full autonomous
development cycle, from goal to implemented code.

MAJOR UPDATE (Phase 5):
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
REFACTORED TO USE UNIX-COMPLIANT WORKFLOW ORCHESTRATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

OLD PATTERN (Removed):
  - Used _ExecutionAgent (mixed code generation + execution)
  - Accepted executor_agent parameter

NEW PATTERN (Current):
  - Uses AutonomousWorkflowOrchestrator
  - Three-phase pipeline: Planning → Specification → Execution
  - No executor_agent parameter needed

UPGRADED (Phase 2): Now uses ContextService for graph-aware context.
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import update
from sqlalchemy.ext.asyncio import AsyncSession

from body.atomic.executor import ActionExecutor
from shared.context import CoreContext
from shared.infrastructure.database.models import Task
from shared.logger import getLogger
from will.agents.coder_agent import CoderAgent
from will.agents.execution_agent import ExecutionAgent
from will.agents.planner_agent import PlannerAgent
from will.agents.specification_agent import SpecificationAgent
from will.orchestration.prompt_pipeline import PromptPipeline
from will.orchestration.workflow_orchestrator import AutonomousWorkflowOrchestrator


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
    task_id: str | None = None,
    output_mode: str = "direct",
):
    """
    Runs the full, end-to-end autonomous development cycle for a given goal.

    REFACTORED: Now uses UNIX-compliant three-phase workflow orchestration.

    Workflow:
    1. Planning (PlannerAgent) → list[ExecutionTask]
    2. Specification (SpecificationAgent) → DetailedPlan with code
    3. Execution (ExecutionAgent) → ExecutionResults

    Args:
        session: Database session for tracking task status
        context: CoreContext with services
        goal: High-level development goal
        task_id: Optional task ID for status tracking
        output_mode: 'direct' or 'crate' mode

    Returns:
        Tuple of (success: bool, result: dict | str)
        - If success: (True, result_dict with files/plan/etc)
        - If failure: (False, error_message_str)

    Note: This function maintains backward compatibility with existing
    callers while using the new UNIX-compliant workflow internally.
    """
    logger.info("🚀 Starting autonomous development cycle for goal: %s", goal)

    # Update task status if tracking
    if task_id and session:
        await session.execute(
            update(Task).where(Task.id == task_id).values(status="planning")
        )
        await session.commit()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHASE 0: RECONNAISSANCE (Optional - Build Context)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    context_report = ""

    try:
        from features.context.context_service import ContextService
        from shared.infrastructure.database.session_manager import (
            get_session as get_new_session,
        )

        logger.debug("Building graph-aware context for goal...")

        context_service = ContextService(
            cognitive_service=context.cognitive_service,
            project_root=str(context.settings.REPO_PATH),
            session_factory=get_new_session,
        )

        context_packet = await context_service.build_for_task(
            {
                "task_id": task_id or "autonomous_dev",
                "task_type": "autonomous_development",
                "summary": goal,
                "scope": {"traversal_depth": 2},
            },
            use_cache=True,
        )

        context_report = _format_context_package_report(context_packet)
        logger.info(
            "✅ Context built: %d relevant items found",
            len(context_packet.get("context", [])),
        )

    except Exception as e:
        logger.warning(
            "Context building failed (proceeding without enhanced context): %s", e
        )
        context_report = ""

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BUILD SPECIALISTS (UNIX-Compliant Three-Phase Pattern)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    logger.debug("Initializing UNIX-compliant workflow specialists...")

    # Get cognitive service
    cognitive_service = context.cognitive_service

    # Try to initialize Qdrant (optional semantic features)
    qdrant_service = None
    try:
        from shared.infrastructure.clients.qdrant_client import QdrantService

        qdrant_service = QdrantService(settings=context.settings)
        logger.debug("Qdrant service initialized")
    except Exception as e:
        logger.debug("Qdrant not available (optional): %s", e)

    # 1. PlannerAgent (Architect)
    planner = PlannerAgent(cognitive_service)

    # 2. CoderAgent (for SpecificationAgent)
    prompt_pipeline = PromptPipeline(context.git_service.repo_path)
    coder_agent = CoderAgent(
        cognitive_service=cognitive_service,
        prompt_pipeline=prompt_pipeline,
        auditor_context=context.auditor_context,
        qdrant_service=qdrant_service,
    )

    # 3. SpecificationAgent (Engineer)
    spec_agent = SpecificationAgent(
        coder_agent=coder_agent,
        context_str="",  # Will accumulate during execution
    )

    # 4. ExecutionAgent (Contractor)
    action_executor = ActionExecutor(context)
    exec_agent = ExecutionAgent(action_executor)

    # 5. AutonomousWorkflowOrchestrator (General Contractor)
    orchestrator = AutonomousWorkflowOrchestrator(
        planner=planner,
        spec_agent=spec_agent,
        exec_agent=exec_agent,
    )

    logger.info("✅ All specialists initialized")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # EXECUTE THREE-PHASE WORKFLOW
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Update task status
    if task_id and session:
        await session.execute(
            update(Task).where(Task.id == task_id).values(status="executing")
        )
        await session.commit()

    try:
        workflow_result = await orchestrator.execute_autonomous_goal(
            goal=goal,
            reconnaissance_report=context_report,
        )

    except Exception as e:
        logger.error("Workflow orchestration failed: %s", e, exc_info=True)

        # Update task status
        if task_id and session:
            await session.execute(
                update(Task).where(Task.id == task_id).values(status="failed")
            )
            await session.commit()

        return (False, f"Workflow failed: {e}")

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # HANDLE RESULTS
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if not workflow_result.success:
        logger.error("Workflow completed with failures")

        # Update task status
        if task_id and session:
            await session.execute(
                update(Task).where(Task.id == task_id).values(status="failed")
            )
            await session.commit()

        return (False, f"Workflow failed: {workflow_result.summary()}")

    # Success!
    logger.info("✅ Workflow completed successfully")

    # Update task status
    if task_id and session:
        await session.execute(
            update(Task).where(Task.id == task_id).values(status="completed")
        )
        await session.commit()

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # BUILD RESULT (Backward Compatible Format)
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    if output_mode == "crate":
        # Extract generated files for crate mode
        generated_files = {}

        for step in workflow_result.detailed_plan.steps:
            if "code" in step.params and step.params.get("file_path"):
                file_path = step.params["file_path"]
                code = step.params["code"]
                generated_files[file_path] = code

        result = {
            "files": generated_files,
            "context_tokens": 0,  # FUTURE: Track if needed
            "generation_tokens": 0,  # FUTURE: Track if needed
            "plan": [
                {
                    "step": step.description,
                    "action": step.action,
                }
                for step in workflow_result.detailed_plan.steps
            ],
            "validation_passed": True,
            "notes": "Generated via UNIX-compliant three-phase workflow",
        }

        return (True, result)

    else:
        # Direct mode - just return success message
        return (True, workflow_result.summary())
