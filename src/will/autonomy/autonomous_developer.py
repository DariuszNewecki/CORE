# src/will/autonomy/autonomous_developer.py

"""
Autonomous Developer - Constitutional Workflow Edition

Replaces hardcoded A3 loop with dynamic workflow composition.
Workflows are defined in .intent/workflows/ and composed from
phases defined in .intent/phases/.

`develop_from_goal` is a compatibility shim over `GoalExecutionWorker`
(will/workers/goal_execution_worker.py) — the genuine Worker that owns
goal-driven execution and its Blackboard evidence lifecycle (#872, ADR-159
D4 thesis-negative adaptation). This function's public signature and
`(bool, str)` return contract are unchanged for its existing CLI/API/
strategic-auditor callers; the WorkflowOrchestrator call itself now happens
inside the Worker's own `run()`, driven through the real `Worker.start()`
lifecycle (registration, liveness lease, silence enforcement, uncaught-error
Blackboard reporting).
"""

from __future__ import annotations

from shared.context import CoreContext
from shared.logger import getLogger
from will.workers.goal_execution_worker import GoalExecutionWorker


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

    worker = GoalExecutionWorker(
        context=context,
        goal=goal,
        workflow_type=workflow_type,
        write=write,
        task_id=task_id,
    )

    try:
        await worker.start()
    except Exception as e:
        logger.error("Autonomous development failed: %s", e, exc_info=True)
        return (False, f"Execution error: {e}")

    result = worker.result
    assert result is not None, (
        "GoalExecutionWorker.start() returned without raising, but "
        "run() did not set self.result — this should be unreachable."
    )

    if result.ok:
        message = f"Workflow '{workflow_type}' completed successfully (run_id={worker.run_id})"
        return (True, message)
    else:
        failed_phase = next(
            (p.name for p in result.phase_results if not p.ok), "unknown"
        )
        message = f"Workflow failed at phase: {failed_phase} (run_id={worker.run_id})"
        return (False, message)


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

    # Default: code changes that aren't test generation use refactor_modularity.
    # full_feature_development is not a registered workflow — it would route
    # through generate_changes just as refactor_modularity does.
    logger.warning("Could not infer workflow type, defaulting to refactor_modularity")
    return "refactor_modularity"
