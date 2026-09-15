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

from types import MappingProxyType

from shared.context import CoreContext
from shared.logger import getLogger
from will.workers.goal_execution_worker import GoalExecutionWorker


logger = getLogger(__name__)


# ADR-160 D3 rolls out develop_from_goal's proposal-gating default one caller
# at a time (Governor ruling, 2026-09-12 Note, "D3 rolls out one caller at a
# time; POST /develop/goal first"). This polarity inversion makes
# create_proposal_only=True the FAIL-CLOSED DEFAULT for every write
# request; the four callers below are grandfathered onto today's direct-write
# behavior by explicitly passing `legacy_direct_write=True` until each is
# separately authorized and converted. Converting one caller never authorizes
# converting another. `POST /develop/goal` (development_routes.py) is not in
# this registry — it was the first conversion and now gets the fail-closed
# default for free, with no opt-out.
#
# This list is MONOTONICALLY SHRINKING. Adding an entry requires a Governor
# ruling — it is not a decision Claude Code or CORE itself may make.
#
# This is NOT a declarative-only gate of the kind ADR-160's Context section
# criticises (CommandExposure.GOVERNOR_ONLY, Worker.approval_required — both
# read by nothing at runtime). This registry is read and enforced:
# tests/will/autonomy/test_legacy_direct_write_registry.py scans src/ for
# every `legacy_direct_write=True` call site and asserts the set equals
# exactly this mapping's keys. A caller that opts out without a matching
# entry fails CI; a registry entry with no corresponding call site also
# fails CI.
_GRANDFATHERED_DIRECT_WRITE_CALLERS: MappingProxyType[str, str] = MappingProxyType(
    {
        "cli.resources.dev.refactor": (
            "removal condition not yet determined — Governor ruling required "
            "(tracked: #883)"
        ),
        "will.governance.refactor_runner": (
            "core.refactor_runs' status lifecycle (_update_refactor_run_status) "
            "has only 'completed'/'failed' terminal states and no "
            "pending-approval state; create_proposal_only=True would mark a "
            "run 'completed' when only a Proposal was created, misreporting "
            "it to any reader of GET /refactor/runs."
        ),
        "will.self_healing.modularity_remediation_service": (
            "issue #877 (Logic Conservation Gate read-after-write) — "
            "remediate_batch reads the file back immediately after "
            "develop_from_goal returns to score the conservation ratio; "
            "create_proposal_only=True would return before any write occurs, "
            "so the read-after-write check would run against unchanged "
            "content."
        ),
        "will.agents.strategic_auditor.effects": (
            "core.tasks' closed-vocab CHECK (pending/planning/executing/"
            "validating/completed/failed/blocked) has no pending-approval "
            "state; execute_approved_clusters' "
            "repo.update_status(child.id, 'completed' if success else "
            "'failed') would mark a cluster 'completed' when only a "
            "Proposal was created, misrepresenting the campaign's "
            "per-cluster review handle."
        ),
    }
)


# Stable token on develop_from_goal's message when the run was UNAVAILABLE
# (planner prompt / cognitive-role client unobtainable). Callers that need
# the distinction (runtime external-run's exit code) check startswith().
UNAVAILABLE_PREFIX = "UNAVAILABLE: "


# ID: ad8b2dd6-6874-431f-9fba-9d22a2d6a04c
async def develop_from_goal(
    context: CoreContext,
    goal: str,
    workflow_type: str,
    write: bool = False,
    task_id: str | None = None,
    legacy_direct_write: bool = False,
) -> tuple[bool, str]:
    """
    Execute a goal using constitutional workflow orchestration.

    Args:
        context: Core context with services
        goal: High-level objective
        workflow_type: Which workflow to use (refactor_modularity, coverage_remediation, etc.)
        write: Whether to apply changes
        task_id: Optional task ID for tracking
        legacy_direct_write: ADR-160 D3 polarity inversion, default False.
            The fail-closed default is now create_proposal_only=True for any
            write-capable request: the goal is planned and converted to a
            Proposal, persisted in PENDING, and left pending Governor approval
            — no write occurs regardless of `write`. Passing
            `legacy_direct_write=True` opts a grandfathered caller back into
            today's direct-write behavior; see
            `_GRANDFATHERED_DIRECT_WRITE_CALLERS` above for which callers and
            why. New callers must not pass this argument.

    Returns:
        (success, message) tuple. In proposal-gated mode (the default for a
        write-capable request), `message` names the created Proposal
        (pending approval) rather than reporting a completed workflow — the
        caller must not read this as "work was applied."

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

    # ADR-160 D3 polarity inversion: fail-closed by default. A write-capable
    # request is Proposal-gated unless a grandfathered caller explicitly
    # opts out via `legacy_direct_write=True` (see
    # _GRANDFATHERED_DIRECT_WRITE_CALLERS above).
    create_proposal_only = write and not legacy_direct_write

    worker = GoalExecutionWorker(
        context=context,
        goal=goal,
        workflow_type=workflow_type,
        write=write,
        task_id=task_id,
        create_proposal_only=create_proposal_only,
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

    # #894 Unit 3: explicit unavailability is its own outcome, never folded
    # into "failed at phase X". The worker already recorded it on the
    # Blackboard (goal_run.<run_id>.outcome, instrument_result=unavailable);
    # this message is the stable, machine-checkable form for callers that
    # only see (ok, message) -- it always starts with UNAVAILABLE_PREFIX.
    if worker.unavailable_reason is not None:
        return (
            False,
            f"{UNAVAILABLE_PREFIX}{worker.unavailable_reason} (run_id={worker.run_id})",
        )

    if create_proposal_only:
        if result.ok and worker.proposal_id:
            message = (
                f"Proposal {worker.proposal_id} created "
                f"(approval_required={worker.proposal_approval_required}), "
                f"pending Governor approval (run_id={worker.run_id})"
            )
            return (True, message)
        failure_detail = next(
            (p.error for p in result.phase_results if not p.ok), "unknown reason"
        )
        message = (
            f"Plan could not be converted to a Proposal: {failure_detail} "
            f"(run_id={worker.run_id})"
        )
        return (False, message)

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
