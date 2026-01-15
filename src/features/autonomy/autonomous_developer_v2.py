# src/features/autonomy/autonomous_developer_v2.py
# ID: features.autonomy.autonomous_developer_v2

"""
Autonomous Developer V2 - Constitutional Workflow Edition

Replaces hardcoded A3 loop with dynamic workflow composition.
Workflows are defined in .intent/workflows/ and composed from
phases defined in .intent/phases/.

BREAKING CHANGE: This is the new interface for autonomous operations.
"""

from __future__ import annotations

from typing import Any

from shared.context import CoreContext
from shared.logger import getLogger
from shared.models.workflow_models import PhaseWorkflowResult
from will.orchestration.phase_registry import PhaseRegistry
from will.orchestration.workflow_orchestrator import WorkflowOrchestrator


logger = getLogger(__name__)


# ID: 3c4d5e6f-7g8h-9i0j-1k2l-3m4n5o6p7q8r
# ID: ee765f17-55bd-4009-b341-fbabaa0faa9c
async def develop_from_goal_v2(
    context: CoreContext,
    goal: str,
    workflow_type: str,
    write: bool = False,
    task_id: str | None = None,
) -> tuple[bool, str]:
    """
    Execute a goal using constitutional workflow orchestration.

    Args:
        context: Core context with services
        goal: High-level objective
        workflow_type: Which workflow to use (refactor_modularity, coverage_remediation, etc.)
        write: Whether to apply changes
        task_id: Optional task ID for tracking

    Returns:
        (success, message) tuple

    Examples:
        # Refactor for modularity
        await develop_from_goal_v2(
            context,
            "Improve modularity of user_service.py",
            "refactor_modularity",
            write=True
        )

        # Generate missing tests
        await develop_from_goal_v2(
            context,
            "Generate tests for payment_processor.py",
            "coverage_remediation",
            write=True
        )
    """
    logger.info("🚀 Autonomous Development V2")
    logger.info("Goal: %s", goal)
    logger.info("Workflow: %s", workflow_type)
    logger.info("Write: %s", write)

    try:
        # Initialize orchestrator
        phase_registry = PhaseRegistry(context)
        orchestrator = WorkflowOrchestrator(phase_registry)

        # Execute workflow
        result: PhaseWorkflowResult = await orchestrator.execute_goal(
            goal=goal,
            workflow_type=workflow_type,
            write=write,
        )

        if result.ok:
            message = f"Workflow '{workflow_type}' completed successfully"
            return (True, message)
        else:
            failed_phase = next(
                (p.name for p in result.phase_results if not p.ok), "unknown"
            )
            message = f"Workflow failed at phase: {failed_phase}"
            return (False, message)

    except Exception as e:
        logger.error("Autonomous development failed: %s", e, exc_info=True)
        return (False, f"Execution error: {e}")


# ID: 4d5e6f7g-8h9i-0j1k-2l3m-4n5o6p7q8r9s
# ID: 1fc0652d-f38f-4dc5-b564-1bd15ffaff17
def infer_workflow_type(goal: str) -> str:
    """
    Infer workflow type from goal text.

    This is a simple heuristic - could be made smarter with LLM analysis.
    """
    goal_lower = goal.lower()

    # Refactoring signals
    if any(
        word in goal_lower for word in ["refactor", "modularity", "split", "extract"]
    ):
        return "refactor_modularity"

    # Test generation signals
    if any(word in goal_lower for word in ["test", "coverage", "generate tests"]):
        return "coverage_remediation"

    # Feature development signals
    if any(word in goal_lower for word in ["implement", "add feature", "create"]):
        return "full_feature_development"

    # Default to full feature development
    logger.warning(
        "Could not infer workflow type, defaulting to full_feature_development"
    )
    return "full_feature_development"


# Backward compatibility wrapper
# ID: 5e6f7g8h-9i0j-1k2l-3m4n-5o6p7q8r9s0t
# ID: bbba4194-fa76-42a0-8911-b8bfb7ad9ac9
async def develop_from_goal(
    session: Any,  # Kept for compatibility, not used
    context: CoreContext,
    goal: str,
    task_id: str | None = None,
    output_mode: str = "direct",
    write: bool = False,
) -> tuple[bool, str]:
    """
    Legacy interface for backward compatibility.

    Automatically infers workflow type from goal.
    New code should use develop_from_goal_v2 with explicit workflow_type.
    """
    workflow_type = infer_workflow_type(goal)

    logger.info("🔄 Legacy interface: Inferred workflow type '%s'", workflow_type)

    return await develop_from_goal_v2(
        context=context,
        goal=goal,
        workflow_type=workflow_type,
        write=write,
        task_id=task_id,
    )
