# tests/will/workers/test_goal_execution_worker.py
"""GoalExecutionWorker — genuine Worker-owned goal execution + Blackboard
evidence lifecycle (#872, ADR-159 D4 thesis-negative adaptation).

No real DB or blackboard: `_register`/`_release_held_claims` (DB-touching
lifecycle leaves) and `_blackboard` (the BlackboardPublisher DB write
surface) are mocked; `WorkflowOrchestrator`/`PhaseRegistry` are patched at
their import site in the module under test. `__init__` is NOT bypassed —
it loads the real `.intent/workers/goal_execution_worker.yaml` declaration,
so a schema/loader break would fail these tests too.
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from shared.models.workflow_models import PhaseResult, PhaseWorkflowResult
from shared.workers.base import WorkerSilenceError
from will.workers.goal_execution_worker import GoalExecutionWorker


async def _never_returns() -> None:
    await asyncio.Event().wait()


def _make_worker(**overrides: object) -> GoalExecutionWorker:
    """Real __init__ (loads the real .intent/ declaration); DB-touching
    lifecycle leaves and the blackboard write surface are faked out."""
    context = MagicMock()
    context.path_resolver = MagicMock()
    context.cognitive_service = MagicMock()
    context.qdrant_service = MagicMock()

    kwargs = {
        "context": context,
        "goal": "Improve modularity of demo.py",
        "workflow_type": "refactor_modularity",
        "write": False,
        "task_id": "task-1",
    }
    kwargs.update(overrides)

    worker = GoalExecutionWorker(**kwargs)  # type: ignore[arg-type]
    worker._register = AsyncMock()  # type: ignore[method-assign]
    worker._release_held_claims = AsyncMock(return_value=0)  # type: ignore[method-assign]
    worker._renew_lease_until_cancelled = _never_returns  # type: ignore[method-assign]
    worker._blackboard = AsyncMock()
    return worker


def _success_result(plan: dict[str, object]) -> PhaseWorkflowResult:
    return PhaseWorkflowResult(
        ok=True,
        workflow_type="refactor_modularity",
        total_duration=1.23,
        phase_results=[
            PhaseResult(name="interpret", ok=True, data={}, duration_sec=0.1),
            PhaseResult(name="parse", ok=True, data=plan, duration_sec=0.2),
            PhaseResult(name="execution", ok=True, data={}, duration_sec=0.5),
        ],
    )


def _failed_phase_result() -> PhaseWorkflowResult:
    return PhaseWorkflowResult(
        ok=False,
        workflow_type="refactor_modularity",
        total_duration=0.9,
        phase_results=[
            PhaseResult(name="interpret", ok=True, data={}, duration_sec=0.1),
            PhaseResult(name="parse", ok=True, data={"actions": ["x"]}, duration_sec=0.2),
            PhaseResult(name="audit", ok=False, data={}, error="canary failed", duration_sec=0.3),
        ],
    )


def _criteria_not_met_result() -> PhaseWorkflowResult:
    """Every phase ok=True but the workflow's overall ok is False — the
    orchestrator's success_criteria mismatch, with no phase-level reason."""
    return PhaseWorkflowResult(
        ok=False,
        workflow_type="refactor_modularity",
        total_duration=0.5,
        phase_results=[
            PhaseResult(name="interpret", ok=True, data={}, duration_sec=0.1),
            PhaseResult(name="parse", ok=True, data={}, duration_sec=0.1),
            PhaseResult(name="execution", ok=True, data={}, duration_sec=0.3),
        ],
    )


def _patched_orchestrator(result: PhaseWorkflowResult):
    executor_instance = MagicMock()
    executor_instance.execute_goal = AsyncMock(return_value=result)
    return patch(
        "will.workers.goal_execution_worker.WorkflowOrchestrator",
        return_value=executor_instance,
    ), patch("will.workers.goal_execution_worker.PhaseRegistry")


# --------------------------------------------------------------------------- lifecycle


async def test_start_exercises_real_lifecycle_and_registers() -> None:
    """`start()` — not bypassed — really calls _register, run(), and cleanup."""
    worker = _make_worker()

    async def _run_and_post() -> None:
        await worker.post_report("goal_run.x.start", {})

    worker.run = AsyncMock(side_effect=_run_and_post)  # type: ignore[method-assign]

    await worker.start()

    worker._register.assert_awaited_once()
    worker.run.assert_awaited_once()
    worker._release_held_claims.assert_awaited_once()


async def test_silent_run_raises_worker_silence_error() -> None:
    """A run() that posts nothing must not pass start() unnoticed."""
    worker = _make_worker()
    with patch.object(GoalExecutionWorker, "run", new=AsyncMock(return_value=None)):
        with pytest.raises(WorkerSilenceError):
            await worker.start()


# --------------------------------------------------------------------------- outcomes


async def test_success_posts_correlated_start_and_outcome_with_plan() -> None:
    worker = _make_worker()
    plan = {"selected_actions": ["split_module"]}
    orch_patch, registry_patch = _patched_orchestrator(_success_result(plan))

    with orch_patch, registry_patch:
        await worker.run()

    assert worker.run_id
    assert worker.result is not None and worker.result.ok is True

    start_call = worker._blackboard.post_report.call_args_list[0]
    outcome_call = worker._blackboard.post_report.call_args_list[1]

    start_subject, start_payload = start_call.args
    outcome_subject, outcome_payload = outcome_call.args

    assert start_subject == f"goal_run.{worker.run_id}.start"
    assert start_payload["goal"] == "Improve modularity of demo.py"
    assert start_payload["run_id"] == worker.run_id

    assert outcome_subject == f"goal_run.{worker.run_id}.outcome"
    assert outcome_payload["ok"] is True
    assert outcome_payload["plan"] == plan
    assert outcome_payload["run_id"] == worker.run_id

    worker._blackboard.post_observation.assert_not_called()


async def test_failed_phase_posts_observation_with_reason() -> None:
    worker = _make_worker()
    orch_patch, registry_patch = _patched_orchestrator(_failed_phase_result())

    with orch_patch, registry_patch:
        await worker.run()

    assert worker.result is not None and worker.result.ok is False
    subject, payload = worker._blackboard.post_observation.call_args.args
    status = worker._blackboard.post_observation.call_args.kwargs["status"]

    assert subject == f"goal_run.{worker.run_id}.outcome"
    assert status == "abandoned"
    assert payload["failed_phase"] == "audit"
    assert payload["reason"] == "canary failed"
    assert payload["ok"] is False


async def test_success_criteria_not_met_is_reported_unavailable_not_abandoned() -> None:
    """No phase failed, but overall ok=False — an honest 'unavailable',
    distinct from a phase-attributed failure/refusal."""
    worker = _make_worker()
    orch_patch, registry_patch = _patched_orchestrator(_criteria_not_met_result())

    with orch_patch, registry_patch:
        await worker.run()

    subject, payload = worker._blackboard.post_observation.call_args.args
    status = worker._blackboard.post_observation.call_args.kwargs["status"]

    assert subject == f"goal_run.{worker.run_id}.outcome"
    assert status == "indeterminate"
    assert payload["instrument_result"] == "unavailable"
    assert payload["reason"] == "success_criteria_not_met_no_phase_reason"


async def test_orchestrator_exception_posts_abandoned_observation_and_reraises() -> None:
    worker = _make_worker()
    executor_instance = MagicMock()
    executor_instance.execute_goal = AsyncMock(side_effect=RuntimeError("boom"))

    with (
        patch(
            "will.workers.goal_execution_worker.WorkflowOrchestrator",
            return_value=executor_instance,
        ),
        patch("will.workers.goal_execution_worker.PhaseRegistry"),
        pytest.raises(RuntimeError, match="boom"),
    ):
        await worker.run()

    subject, payload = worker._blackboard.post_observation.call_args.args
    status = worker._blackboard.post_observation.call_args.kwargs["status"]
    assert subject == f"goal_run.{worker.run_id}.outcome"
    assert status == "abandoned"
    assert payload["error"] == "boom"
    # The start report still landed before the crash — not silently lost.
    worker._blackboard.post_report.assert_called_once()


async def test_missing_path_resolver_posts_unavailable_before_raising() -> None:
    worker = _make_worker()
    worker._context.path_resolver = None

    with pytest.raises(RuntimeError, match="PathResolver"):
        await worker.run()

    subject, kwargs_reason = (
        worker._blackboard.post_observation.call_args.args,
        worker._blackboard.post_observation.call_args.kwargs,
    )
    assert subject[0] == f"goal_run.{worker.run_id}.outcome"
    assert kwargs_reason["status"] == "indeterminate"
    assert subject[1]["reason"] == "path_resolver_missing"


# ------------------------------------------------------- declared scope conformance

# The real action_ids reachable from the two currently-supported workflows
# (refactor_modularity, coverage_remediation), per direct trace of
# .intent/workflows/definitions/*.yaml and .intent/workflows/stages/*.yaml —
# not a placeholder. If a workflow starts requiring a new action_id, this
# test fails and the declaration must be updated deliberately, not silently.
_WORKFLOW_ACTION_IDS = {
    "intent.normalize",
    "intent.classify",
    "workflow.select",
    "action.plan",
    "scope.assess",
    "context.resolve",
    "action.resolve",
    "change.generate",
    "test.canary_validate",
    "style.validate",
    "style.autofix",
    "audit.evaluate",
    "change.commit",
    "test.generate",
    "test.sandbox_validate",
}


def test_declared_permitted_tools_cover_both_supported_workflows() -> None:
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    repo = get_intent_repository()
    repo.initialize()
    declaration = repo.load_worker("workers/goal_execution_worker")
    declared_tools = set(declaration["mandate"]["permitted_tools"])

    assert _WORKFLOW_ACTION_IDS <= declared_tools
    # No hypothetical/future grant beyond what the two workflows use today.
    assert declared_tools == _WORKFLOW_ACTION_IDS


def test_declared_scope_paths_match_workflow_invariants() -> None:
    from shared.infrastructure.intent.intent_repository import get_intent_repository

    repo = get_intent_repository()
    repo.initialize()
    declaration = repo.load_worker("workers/goal_execution_worker")
    paths = set(declaration["mandate"]["scope"]["paths"])

    # refactor_modularity writes src/**; coverage_remediation writes tests/**
    # (each forbidden from the other tree by its own workflow invariant) —
    # the declaration is their union, not a broadened grant.
    assert paths == {"src/**", "tests/**"}
