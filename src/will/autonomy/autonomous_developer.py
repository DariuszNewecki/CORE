# src/body/autonomy/autonomous_developer.py

"""
Autonomous Developer - Constitutional Workflow Edition

Replaces hardcoded A3 loop with dynamic workflow composition.
Workflows are defined in .intent/workflows/ and composed from
phases defined in .intent/phases/.
"""

from __future__ import annotations

from shared.context import CoreContext
from shared.logger import getLogger
from shared.models.workflow_models import PhaseWorkflowResult
from will.orchestration.phase_registry import PhaseRegistry
from will.orchestration.workflow_orchestrator import WorkflowOrchestrator


logger = getLogger(__name__)


# ID: ad8b2dd6-6874-431f-9fba-9d22a2d6a04c
async def develop_from_goal(
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
        await develop_from_goal(
            context,
            "Improve modularity of user_service.py",
            "refactor_modularity",
            write=True
        )

        # Generate missing tests
        await develop_from_goal(
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

    path_resolver = getattr(context, "path_resolver", None)
    if not path_resolver:
        raise RuntimeError(
            "PathResolver not found in CoreContext. "
            "Ensure src/body/infrastructure/bootstrap.py has been updated to v2.6."
        )

    try:
        # Initialize orchestrator with PathResolver (FIXED)
        phase_registry = PhaseRegistry(context, path_resolver)
        orchestrator = WorkflowOrchestrator(phase_registry, path_resolver)

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


# ID: 9ec4f0d3-c06c-483f-83ac-b01c52746f24
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
