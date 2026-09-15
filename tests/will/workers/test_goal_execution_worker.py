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

from shared.models.execution_models import ExecutionTask, TaskParams
from shared.models.workflow_models import PhaseResult, PhaseWorkflowResult
from shared.workers.base import WorkerSilenceError
from will.workers.goal_execution_worker import GoalExecutionWorker


async def _never_returns() -> None:
    await asyncio.Event().wait()


@pytest.fixture(autouse=True)
def _planner_ready(request):
    """#894 Unit 3: run() probes planner readiness before planning. The
    existing tests model a ready apparatus; the unavailable path has its own
    tests below (marked with the `planner_unavailable` fixture)."""
    if "planner_unavailable" in request.fixturenames:
        yield
        return
    with patch(
        "will.workers.goal_execution_worker.probe_planner_readiness",
        new=AsyncMock(return_value=None),
    ):
        yield


@pytest.fixture
def planner_unavailable():
    with patch(
        "will.workers.goal_execution_worker.probe_planner_readiness",
        new=AsyncMock(
            return_value="no cognitive-role client for planner role 'planner'"
        ),
    ):
        yield


def _make_worker(**overrides: object) -> GoalExecutionWorker:
    """Real __init__ (loads the real .intent/ declaration); DB-touching
    lifecycle leaves and the blackboard write surface are faked out."""
    context = MagicMock()
    context.path_resolver = MagicMock()
    context.cognitive_service = MagicMock()
    context.qdrant_service = MagicMock()
    # Real str, not a MagicMock: create_proposal_only's PlannerAgent
    # construction does Path(context.git_service.repo_path) for real
    # (PlannerAgent itself is patched in those tests, but this call happens
    # in goal_execution_worker.py's own code, before the patched class).
    context.git_service.repo_path = "/repo"

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
            PhaseResult(
                name="parse", ok=True, data={"actions": ["x"]}, duration_sec=0.2
            ),
            PhaseResult(
                name="audit", ok=False, data={}, error="canary failed", duration_sec=0.3
            ),
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


def _real_plan_data() -> dict[str, object]:
    """What ParsePhase actually leaves under data: pydantic ExecutionTask
    objects (CodeGenerationPhase's input), not JSON."""
    return {
        "execution_plan": [
            ExecutionTask(
                step="Add a docstring",
                action="fix.docstrings",
                params=TaskParams(file_path="package/mod.py"),
            )
        ],
        "steps_count": 1,
        "goal": "Evaluate the package",
    }


def _failed_after_real_plan_result() -> PhaseWorkflowResult:
    return PhaseWorkflowResult(
        ok=False,
        workflow_type="code_modification",
        total_duration=19.0,
        phase_results=[
            PhaseResult(name="interpret", ok=True, data={}, duration_sec=0.0),
            PhaseResult(
                name="parse", ok=True, data=_real_plan_data(), duration_sec=3.0
            ),
            PhaseResult(
                name="runtime",
                ok=False,
                data={},
                error="Schema not found: .../var/context/schema.yaml",
                duration_sec=1.0,
            ),
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


async def test_orchestrator_exception_posts_abandoned_observation_and_reraises() -> (
    None
):
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


# --------------------------------------------------- create_proposal_only (ADR-160 D3)


def _task(action: str, file_path: str | None) -> ExecutionTask:
    return ExecutionTask(
        step="step", action=action, params=TaskParams(file_path=file_path)
    )


class _FakeSessionCM:
    """Minimal async context manager standing in for
    `service_registry.session()` — yields a fake session, no real DB."""

    def __init__(self, session: MagicMock) -> None:
        self._session = session

    async def __aenter__(self) -> MagicMock:
        return self._session

    async def __aexit__(self, *exc: object) -> bool:
        return False


def test_default_create_proposal_only_is_false() -> None:
    worker = _make_worker()
    assert worker.create_proposal_only is False


async def test_create_proposal_only_success_persists_pending_and_never_touches_orchestrator() -> (
    None
):
    """A convertible plan creates a PENDING Proposal via ProposalRepository
    and reports its id — WorkflowOrchestrator/ActionExecutor are never
    reached, so no write occurs regardless of `write`. PENDING, not a
    holding state: the Proposal must be visible in the approval queue
    from the moment it exists (#885)."""
    worker = _make_worker(
        workflow_type="code_modification", write=True, create_proposal_only=True
    )

    fake_planner = MagicMock()
    fake_planner.create_execution_plan = AsyncMock(
        return_value=[_task("file.edit", "src/foo.py")]
    )

    fake_session = MagicMock()
    fake_session.commit = AsyncMock()
    fake_repo = MagicMock()
    fake_repo.create = AsyncMock(return_value="proposal-123")

    orchestrator_never_called = MagicMock()
    orchestrator_never_called.execute_goal = AsyncMock(
        side_effect=AssertionError(
            "orchestrator must not run in create_proposal_only mode"
        )
    )

    with (
        patch("will.agents.planner_agent.PlannerAgent", return_value=fake_planner),
        patch(
            "will.autonomy.proposal_repository.ProposalRepository",
            return_value=fake_repo,
        ),
        patch("body.services.service_registry.service_registry") as fake_registry,
        patch(
            "will.workers.goal_execution_worker.WorkflowOrchestrator",
            return_value=orchestrator_never_called,
        ),
        patch("will.workers.goal_execution_worker.PhaseRegistry"),
    ):
        fake_registry.session = MagicMock(return_value=_FakeSessionCM(fake_session))
        await worker.run()

    orchestrator_never_called.execute_goal.assert_not_called()
    fake_repo.create.assert_awaited_once()
    fake_session.commit.assert_awaited_once()

    from will.autonomy.proposal import Proposal, ProposalStatus

    (created,) = fake_repo.create.call_args.args
    assert isinstance(created, Proposal)
    assert created.status is ProposalStatus.PENDING
    assert created.created_by == "api.develop_goal"

    assert worker.proposal_id == "proposal-123"
    # file.edit resolves to `moderate` in action_risk.yaml -> requires approval.
    assert worker.proposal_approval_required is True
    assert worker.result is not None and worker.result.ok is True

    outcome_call = worker._blackboard.post_report.call_args_list[-1]
    _, payload = outcome_call.args
    assert payload["mode"] == "create_proposal_only"
    assert payload["proposal_id"] == "proposal-123"
    assert payload["approval_required"] is True
    assert payload["scope_files"] == ["src/foo.py"]
    worker._blackboard.post_observation.assert_not_called()


async def test_create_proposal_only_refuses_on_refactor_modularity() -> None:
    """refactor_modularity bypasses the planner's own action choice
    entirely -- the plan cannot describe what will execute, so the
    converter refuses and no Proposal is created."""
    worker = _make_worker(
        workflow_type="refactor_modularity", write=True, create_proposal_only=True
    )

    fake_planner = MagicMock()
    fake_planner.create_execution_plan = AsyncMock(
        return_value=[_task("refactor.apply_split", "src/big.py")]
    )
    fake_repo = MagicMock()
    fake_repo.create = AsyncMock()

    with (
        patch("will.agents.planner_agent.PlannerAgent", return_value=fake_planner),
        patch(
            "will.autonomy.proposal_repository.ProposalRepository",
            return_value=fake_repo,
        ),
    ):
        await worker.run()

    fake_repo.create.assert_not_called()
    assert worker.proposal_id is None
    assert worker.result is not None and worker.result.ok is False

    subject, payload = worker._blackboard.post_observation.call_args.args
    assert subject == f"goal_run.{worker.run_id}.outcome"
    assert payload["reason"] == "plan_conversion_refused"
    assert "refactor_modularity" in payload["detail"]


async def test_create_proposal_only_refuses_on_planning_exception() -> None:
    worker = _make_worker(
        workflow_type="code_modification", write=True, create_proposal_only=True
    )
    fake_planner = MagicMock()
    fake_planner.create_execution_plan = AsyncMock(side_effect=RuntimeError("llm down"))

    with patch("will.agents.planner_agent.PlannerAgent", return_value=fake_planner):
        await worker.run()

    assert worker.result is not None and worker.result.ok is False
    _, payload = worker._blackboard.post_observation.call_args.args
    assert payload["reason"] == "planning_failed"
    assert "llm down" in payload["detail"]


async def test_create_proposal_only_refuses_on_empty_plan() -> None:
    worker = _make_worker(
        workflow_type="code_modification", write=True, create_proposal_only=True
    )
    fake_planner = MagicMock()
    fake_planner.create_execution_plan = AsyncMock(return_value=[])

    with patch("will.agents.planner_agent.PlannerAgent", return_value=fake_planner):
        await worker.run()

    assert worker.result is not None and worker.result.ok is False
    _, payload = worker._blackboard.post_observation.call_args.args
    assert payload["reason"] == "empty_plan"


async def test_create_proposal_only_refuses_high_risk_proposal_unapproved() -> None:
    """A dangerous-classified action resolves to Proposal overall_risk
    'high'; Proposal.validate() requires approved_by for high-risk
    proposals, which create_proposal_only mode never sets -- refuse
    rather than persist an invalid Proposal."""
    worker = _make_worker(
        workflow_type="code_modification", write=True, create_proposal_only=True
    )
    fake_planner = MagicMock()
    fake_planner.create_execution_plan = AsyncMock(
        return_value=[_task("fix.vulture_heal", "src/dead.py")]
    )
    fake_repo = MagicMock()
    fake_repo.create = AsyncMock()

    with (
        patch("will.agents.planner_agent.PlannerAgent", return_value=fake_planner),
        patch(
            "will.autonomy.proposal_repository.ProposalRepository",
            return_value=fake_repo,
        ),
    ):
        await worker.run()

    fake_repo.create.assert_not_called()
    assert worker.result is not None and worker.result.ok is False
    _, payload = worker._blackboard.post_observation.call_args.args
    assert payload["reason"] == "proposal_invalid"


# --- #894 Unit 3: run identity carries the binding; unavailability is recorded ---


def _binding():
    from shared.models.target_binding import DisplacedFile, TargetBinding

    return TargetBinding(
        subject_path="/subjects/frozen",
        subject_sha="a" * 40,
        subject_tree_hash="b" * 40,
        bound_repo_path="/evidence/runs/r1/target",
        bound_sha="c" * 40,
        bound_tree_hash="d" * 40,
        floor_hash="e" * 64,
        overlay_hash="f" * 64,
        displaced=(DisplacedFile("META/enums.json", "1" * 64, "2" * 64),),
    )


async def test_internal_run_start_payload_has_no_target_binding_key() -> None:
    """Preserve internal-run payloads exactly: the key is omitted, not null."""
    worker = _make_worker()
    worker._context.target_binding = None
    orch_patch, registry_patch = _patched_orchestrator(_success_result({}))
    with orch_patch, registry_patch:
        await worker.run()
    _, start_payload = worker._blackboard.post_report.call_args_list[0].args
    assert "target_binding" not in start_payload


async def test_bound_run_start_payload_carries_the_binding() -> None:
    worker = _make_worker()
    worker._context.target_binding = _binding()
    orch_patch, registry_patch = _patched_orchestrator(_success_result({}))
    with orch_patch, registry_patch:
        await worker.run()
    _, start_payload = worker._blackboard.post_report.call_args_list[0].args
    tb = start_payload["target_binding"]
    assert tb["subject_sha"] == "a" * 40
    assert tb["bound_tree_hash"] == "d" * 40
    assert tb["floor_hash"] == "e" * 64 and tb["overlay_hash"] == "f" * 64
    assert tb["displaced"] == [
        {
            "path": "META/enums.json",
            "original_sha256": "1" * 64,
            "installed_floor_sha256": "2" * 64,
        }
    ]


async def test_unavailable_planner_is_recorded_on_the_blackboard_and_exposed(
    planner_unavailable,
) -> None:
    """Explicit unavailability is CORE's record: goal_run.<id>.outcome as an
    unavailable instrument result, and worker.unavailable_reason for the shim."""
    worker = _make_worker()
    worker._context.target_binding = _binding()
    orch_patch, registry_patch = _patched_orchestrator(_success_result({}))
    with orch_patch as orch_cls, registry_patch:
        await worker.run()
        orch_cls.return_value.execute_goal.assert_not_called()

    assert worker.unavailable_reason is not None
    assert "planner" in worker.unavailable_reason
    assert worker.result is not None and worker.result.ok is False
    # start was posted (with the binding) ...
    start_subject, start_payload = worker._blackboard.post_report.call_args_list[0].args
    assert start_subject == f"goal_run.{worker.run_id}.start"
    assert "target_binding" in start_payload
    # ... and the outcome is an unavailable observation, not a failure report
    subject, payload = worker._blackboard.post_observation.call_args.args
    status = worker._blackboard.post_observation.call_args.kwargs["status"]
    assert subject == f"goal_run.{worker.run_id}.outcome"
    assert status == "indeterminate"
    assert payload["instrument_result"] == "unavailable"
    assert payload["reason"] == "planner_unavailable"
    assert payload["outcome"] == "unavailable"
    assert payload["run_id"] == worker.run_id


async def test_develop_from_goal_returns_stable_unavailable_message(
    planner_unavailable,
) -> None:
    """The (ok, message) contract is unchanged; UNAVAILABLE is a stable prefix
    the external-run route can check, set explicitly from
    worker.unavailable_reason -- never from a phase error."""
    from will.autonomy import autonomous_developer as ad

    worker = _make_worker()
    orch_patch, registry_patch = _patched_orchestrator(_success_result({}))
    with (
        orch_patch,
        registry_patch,
        patch.object(ad, "GoalExecutionWorker", return_value=worker),
    ):
        ok, message = await ad.develop_from_goal(
            worker._context, "goal", "refactor_modularity", write=False
        )
    assert ok is False
    assert message.startswith(ad.UNAVAILABLE_PREFIX)
    assert worker.run_id in message


async def test_policy_counsel_recorded_only_for_bound_run_without_vector_store() -> (
    None
):
    """Ruling C: `policy_counsel` appears when a target binding is present and
    no qdrant_service is wired; never on an internal run, even with Qdrant down."""
    bound = _make_worker()
    bound._context.target_binding = _binding()
    bound._context.qdrant_service = None
    orch_patch, registry_patch = _patched_orchestrator(_success_result({}))
    with orch_patch, registry_patch:
        await bound.run()
    _, payload = bound._blackboard.post_report.call_args_list[0].args
    assert payload["policy_counsel"].startswith("unavailable")
    assert payload["target_binding"]["seed_hash"] is None

    internal = _make_worker()
    internal._context.target_binding = None
    internal._context.qdrant_service = None  # an internal Qdrant outage
    orch_patch, registry_patch = _patched_orchestrator(_success_result({}))
    with orch_patch, registry_patch:
        await internal.run()
    _, payload = internal._blackboard.post_report.call_args_list[0].args
    assert "policy_counsel" not in payload and "target_binding" not in payload


async def test_policy_counsel_reflects_the_vector_store_resolved_before_the_record() -> (
    None
):
    """The identity record states what the run actually planned with: the
    registry resolution happens BEFORE goal_run.<id>.start is posted. A bound
    run whose registry still hands out a vector store (the ruling C leak the
    live run found) must not record "unavailable" while PARSE then uses it."""
    bound = _make_worker()
    bound._context.target_binding = _binding()
    bound._context.qdrant_service = None
    resolved = MagicMock(name="qdrant_from_registry")
    bound._context.registry.get_qdrant_service = AsyncMock(return_value=resolved)
    orch_patch, registry_patch = _patched_orchestrator(_success_result({}))
    with orch_patch, registry_patch:
        await bound.run()
    _, payload = bound._blackboard.post_report.call_args_list[0].args
    assert "policy_counsel" not in payload, "the run HAD a vector store"
    assert bound._context.qdrant_service is resolved
    bound._context.registry.get_qdrant_service.assert_awaited_once()


# --------------------------------------------------------------------------- plan serialization


@pytest.mark.parametrize(
    ("result", "method"),
    [
        (_success_result(_real_plan_data()), "post_report"),
        (_failed_after_real_plan_result(), "post_observation"),
    ],
    ids=["success", "failed-phase"],
)
async def test_outcome_with_a_real_plan_is_json_serializable(
    result: PhaseWorkflowResult, method: str
) -> None:
    """ParsePhase's plan is list[ExecutionTask]; the Blackboard stores
    json.dumps(payload). Before the fix every outcome path with a real plan
    raised "Object of type ExecutionTask is not JSON serializable" and the
    run's outcome was never recorded (#894 seeded live run)."""
    import json

    worker = _make_worker()
    orch_patch, registry_patch = _patched_orchestrator(result)
    with orch_patch, registry_patch:
        await worker.run()
    poster = getattr(worker._blackboard, method)
    subject, payload = poster.call_args_list[-1].args[:2]
    assert subject == f"goal_run.{worker.run_id}.outcome"
    json.dumps(payload)  # the Blackboard's own serialization must succeed
    steps = payload["plan"]["execution_plan"]
    assert steps == [
        {
            "step": "Add a docstring",
            "action": "fix.docstrings",
            "params": {
                "file_path": "package/mod.py",
                "code": None,
                "symbol_name": None,
                "justification": None,
                "tag": None,
            },
            "task_type": "code_generation",
        }
    ]
    assert payload["plan"]["steps_count"] == 1


async def test_auditor_context_is_resolved_like_the_cli_decorator_does() -> None:
    """A Worker started outside `@core_command` (the external-run route) must
    resolve auditor_context itself; CodeGenerationPhase refuses without it."""
    worker = _make_worker()
    worker._context.auditor_context = None
    resolved = MagicMock(name="auditor_context")
    worker._context.registry.get_auditor_context = AsyncMock(return_value=resolved)
    orch_patch, registry_patch = _patched_orchestrator(_success_result({}))
    with orch_patch, registry_patch:
        await worker.run()
    assert worker._context.auditor_context is resolved

    # a registry that cannot provide one degrades with a warning, not a crash
    worker = _make_worker()
    worker._context.auditor_context = None
    worker._context.registry.get_auditor_context = AsyncMock(
        side_effect=RuntimeError("x")
    )
    orch_patch, registry_patch = _patched_orchestrator(_success_result({}))
    with orch_patch, registry_patch:
        await worker.run()
    assert worker._context.auditor_context is None
