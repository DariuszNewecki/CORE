# src/will/workers/goal_execution_worker.py
"""
GoalExecutionWorker - executes one authorized goal-driven CORE workflow.

Responsibility: own the execution of a single goal-driven WorkflowOrchestrator
run as this Worker's declared unit of constitutional work, and record its
full lifecycle (start, plan, outcome, refusal/failure, or explicit
unavailability) to the Blackboard so an independent reader can reconstruct
the run without relying on process logs.

Constitutional standing:
- Declaration:      .intent/workers/goal_execution_worker.yaml
- Class:            acting
- Phase:            execution
- Permitted tools:  see declaration (the union of action_ids reachable from
                     the refactor_modularity / coverage_remediation workflows)
- Approval:         not declared on this Worker's own YAML — `Worker.
                     approval_required` still has no enforced meaning here
                     (verified: no code reads it off a Worker instance).
                     `Proposal.approval_required` is a separate, unrelated
                     field on the Proposal objects this worker now creates
                     in `create_proposal_only` mode (ADR-160 D3) — see
                     `.intent/workers/violation_remediator.yaml`'s
                     `permitted_tools: []` for the established precedent
                     that Proposal creation is not gated by this
                     declaration's `permitted_tools` field.

LAYER: will/workers — acting worker. Receives CoreContext + the per-call goal
via constructor (one instance per invocation; not scheduler-polled — see
`implementation.requires_dedicated_process` omission in the declaration,
which is a daemon-process-topology concept per ADR-081 that does not apply
to a worker constructed ad hoc by a caller, never registered on a polling
schedule).

`develop_from_goal` (will/autonomy/autonomous_developer.py) is a thin
compatibility shim over this Worker: it constructs one instance per call and
awaits `start()`, which owns registration, the liveness lease, the silence
invariant, and uncaught-error Blackboard reporting (shared/workers/base.py).
This worker's `run()` does not merely wrap that lifecycle for logging
access — it performs the actual WorkflowOrchestrator execution.

Correlation: one `run_id` is minted per execution via the existing
`shared.activity_logging.activity_run` context manager, which also binds it
into the `_current_run_id` contextvar for the duration of the run. This is
the same contextvar `ActionExecutor._audit_log` reads (as a fallback behind
the currently-always-absent `CoreContext.session_id`) when stamping
`core.action_results.action_metadata` — so every action this run performs
is correlated to this run's Blackboard evidence with no new column and no
duplicated persistence.

Out of scope for this worker (ADR-159 D4 / #872): external-target binding,
target reconnaissance/comprehension. This worker executes exactly what
`develop_from_goal` already executed today (CORE-internal goal, direct
ActionExecutor calls) — it adds reconstructable evidence around that
existing, already-governor-gated path; it does not change what that path is
authorized to do.

ADR-160 D3, first staged conversion (`create_proposal_only=True`, opt-in,
default False): plans the goal via `PlannerAgent` directly, converts the
resulting plan to a Proposal via `will.autonomy.plan_to_proposal`, persists
it in PENDING via `ProposalRepository`, and stops — `ActionExecutor` is never
reached in this mode, so this worker now creates Proposals in this one
opt-in path (the "never creates Proposals" claim in earlier revisions of
this docstring covered only the default `orchestrator.execute_goal()` path,
which is unchanged and still creates none).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from shared.activity_logging import activity_run
from shared.logger import getLogger
from shared.models.workflow_models import PhaseResult, PhaseWorkflowResult
from shared.workers.base import Worker
from will.orchestration.phase_registry import PhaseRegistry
from will.orchestration.planner_readiness import probe_planner_readiness
from will.orchestration.workflow_orchestrator import WorkflowOrchestrator


logger = getLogger(__name__)


def _blackboard_safe(value: Any) -> Any:
    """Return *value* with every pydantic model rendered as JSON-safe data.

    ParsePhase leaves the plan under ``data["execution_plan"]`` as
    ``list[ExecutionTask]`` -- the objects CodeGenerationPhase consumes. The
    Blackboard stores ``json.dumps(payload)``, so posting that dict raw fails
    with "Object of type ExecutionTask is not JSON serializable" on EVERY
    outcome path once a plan exists, and the run's outcome is never recorded
    (the #894 seeded live run was the first orchestrator-path run with a
    real plan to reach this line; the ADR-160 create_proposal_only path posts
    no plan). Containers are walked; other values pass through unchanged.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {k: _blackboard_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_blackboard_safe(v) for v in value]
    return value


def _subject_segment(topic: str) -> str:
    """Normalise a recon topic into a dotted blackboard subject segment.

    Topic identity ("artifact_type:infra") is preserved verbatim in the payload;
    the subject uses dots so it reads like every other subject in the system and
    dedup keys stay consistent.
    """
    return topic.replace(":", ".").replace("/", ".").replace(" ", "_")


# ID: ed11bc55-9c7a-4a95-a953-1ce16023104a
class GoalExecutionWorker(Worker):
    """
    Acting worker. Executes exactly one goal-driven CORE workflow via
    WorkflowOrchestrator and records its lifecycle to the Blackboard.

    One instance per invocation — constructed by the caller (today, only
    `develop_from_goal`) with the goal/workflow/write bound at construction
    time, then driven through the normal `Worker.start()` lifecycle.

    `create_proposal_only=True` (ADR-160 D3, opt-in, default False): plans
    the goal directly via `PlannerAgent`, converts the plan to a Proposal
    (`will.autonomy.plan_to_proposal`), persists it in PENDING, and stops —
    `WorkflowOrchestrator`/`ActionExecutor` are never reached in this mode.
    """

    declaration_name = "goal_execution_worker"

    def __init__(
        self,
        *,
        context: Any,
        goal: str,
        workflow_type: str,
        write: bool = False,
        task_id: str | None = None,
        repo_root: Path | None = None,
        create_proposal_only: bool = False,
    ) -> None:
        super().__init__(repo_root=repo_root)
        self._context = context
        self.goal = goal
        self.workflow_type = workflow_type
        self.write = write
        self.task_id = task_id
        self.create_proposal_only = create_proposal_only
        self.run_id: str | None = None
        self.result: PhaseWorkflowResult | None = None
        # #894 Unit 3: set when the apparatus could not run the goal at all
        # (planner prompt or cognitive-role client unobtainable). Recorded on
        # the Blackboard as goal_run.<run_id>.outcome via post_unavailable;
        # develop_from_goal turns it into its stable "UNAVAILABLE: ..." message.
        self.unavailable_reason: str | None = None
        self.proposal_id: str | None = None
        self.proposal_approval_required: bool | None = None

    # ID: 44bb5768-ff92-4abf-9883-0064e6d145a2
    async def run(self) -> None:
        """Execute this Worker's one goal-driven workflow run to completion."""
        with activity_run(
            workflow_id=f"goal_execution.{self.workflow_type}",
            details={"goal": self.goal, "write": self.write, "task_id": self.task_id},
        ) as activity:
            run_id = activity.run_id
            self.run_id = run_id

            start_payload: dict[str, Any] = {
                "run_id": run_id,
                "goal": self.goal,
                "workflow_type": self.workflow_type,
                "write": self.write,
                "task_id": self.task_id,
                "started_at": datetime.now(UTC).isoformat(),
                "action_results_correlation_key": run_id,
            }
            # Resolve the vector store BEFORE the run's identity is written:
            # `policy_counsel` below states what this run actually planned
            # with, so the resolution attempt has to precede the record, not
            # follow it. (Was after the start report; a bound run whose
            # registry still resolved CORE's own Qdrant then recorded
            # "unavailable" while PARSE queried it -- #894 ruling C live run.)
            if self._context.qdrant_service is None:
                try:
                    self._context.qdrant_service = (
                        await self._context.registry.get_qdrant_service()
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not resolve qdrant_service from registry: %s", exc
                    )

            # #894 Unit 3: carry the binding facts when the context has them;
            # a CORE-internal run's payload is unchanged (key omitted, not null).
            binding = getattr(self._context, "target_binding", None)
            if binding is not None:
                start_payload["target_binding"] = binding.to_payload()
                # Ruling C (2026-09-15): an external run has no target-bound
                # policy-vector store (QDRANT_URL is bound empty for it); say
                # so on the run's own identity. Recorded only when a binding
                # is present so an internal Qdrant outage never changes an
                # internal run's payload.
                if self._context.qdrant_service is None:
                    start_payload["policy_counsel"] = (
                        "unavailable — no target-bound policy-vector store"
                    )
            await self.post_report(f"goal_run.{run_id}.start", start_payload)

            path_resolver = getattr(self._context, "path_resolver", None)
            if not path_resolver:
                await self.post_unavailable(
                    f"goal_run.{run_id}.outcome",
                    reason="path_resolver_missing",
                    detail={
                        "run_id": run_id,
                        "goal": self.goal,
                        "workflow_type": self.workflow_type,
                    },
                )
                raise RuntimeError(
                    "PathResolver not found in CoreContext. "
                    "Ensure src/body/infrastructure/bootstrap.py has been updated to v2.6."
                )

            # Warm up the remaining brain services on the CoreContext (the
            # vector store was resolved above, before the identity record):
            # the same three `@core_command(requires_context=True)` resolves
            # for a CLI-entered run, so a Worker started from any other entry
            # point (the pre-bootstrap external-run route, #894) is not short
            # of them. CodeGenerationPhase refuses without auditor_context.
            if self._context.cognitive_service is None:
                try:
                    self._context.cognitive_service = (
                        await self._context.registry.get_cognitive_service()
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not resolve cognitive_service from registry: %s", exc
                    )
            if getattr(self._context, "auditor_context", None) is None:
                try:
                    self._context.auditor_context = (
                        await self._context.registry.get_auditor_context()
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not resolve auditor_context from registry: %s", exc
                    )

            # #894 Unit 3 (item 3 of the ADR-159 remediation scope): explicit
            # unavailability is CORE's own record, not the apparatus's. If the
            # planner cannot obtain its prompt or its cognitive-role client,
            # record goal_run.<run_id>.outcome as an unavailable instrument
            # result and stop -- distinct from a run that planned and failed.
            reason = await probe_planner_readiness(self._context)
            if reason is not None:
                self.unavailable_reason = reason
                await self.post_unavailable(
                    f"goal_run.{run_id}.outcome",
                    reason="planner_unavailable",
                    detail={
                        "run_id": run_id,
                        "goal": self.goal,
                        "workflow_type": self.workflow_type,
                        "detail": reason,
                        "outcome": "unavailable",
                    },
                )
                self.result = PhaseWorkflowResult(
                    ok=False, phase_results=[], workflow_type=self.workflow_type
                )
                return

            if self.create_proposal_only:
                await self._run_create_proposal_only(run_id)
                return

            phase_registry = PhaseRegistry(self._context, path_resolver)
            orchestrator = WorkflowOrchestrator(phase_registry, path_resolver)

            try:
                result = await orchestrator.execute_goal(
                    goal=self.goal,
                    workflow_type=self.workflow_type,
                    write=self.write,
                )
            except Exception as exc:
                await self.post_observation(
                    f"goal_run.{run_id}.outcome",
                    {
                        "run_id": run_id,
                        "goal": self.goal,
                        "workflow_type": self.workflow_type,
                        "ok": False,
                        "error": str(exc),
                    },
                    status="abandoned",
                )
                raise

            self.result = result

            plan_data = _blackboard_safe(
                next((p.data for p in result.phase_results if p.name == "parse"), {})
            )
            phase_summary = [
                {
                    "name": p.name,
                    "ok": p.ok,
                    "duration_sec": p.duration_sec,
                    "error": p.error,
                }
                for p in result.phase_results
            ]

            # Reconnaissance happened before planning, so it is recorded on the
            # run's identity whether or not the run went on to succeed.
            await self._post_reconnaissance_records(run_id, plan_data)
            await self._post_decision_records(run_id, plan_data)

            if result.ok:
                await self.post_report(
                    f"goal_run.{run_id}.outcome",
                    {
                        "run_id": run_id,
                        "ok": True,
                        "workflow_type": result.workflow_type,
                        "plan": plan_data,
                        "phases": phase_summary,
                        "duration_sec": result.total_duration,
                        "action_results_correlation_key": run_id,
                    },
                )
                return

            failed_phase = next((p for p in result.phase_results if not p.ok), None)
            if failed_phase is not None:
                await self.post_observation(
                    f"goal_run.{run_id}.outcome",
                    {
                        "run_id": run_id,
                        "ok": False,
                        "failed_phase": failed_phase.name,
                        "reason": failed_phase.error,
                        "plan": plan_data,
                        "phases": phase_summary,
                        "duration_sec": result.total_duration,
                    },
                    status="abandoned",
                )
            else:
                # Every phase reported ok, but the workflow's own declared
                # success_criteria were not met — no phase-level reason
                # exists to report. Naming this "unavailable" rather than
                # inventing a reason is the honest choice.
                await self.post_unavailable(
                    f"goal_run.{run_id}.outcome",
                    reason="success_criteria_not_met_no_phase_reason",
                    detail={
                        "run_id": run_id,
                        "plan": plan_data,
                        "phases": phase_summary,
                        "duration_sec": result.total_duration,
                    },
                )

    # ID: a1fb17c6-a4a7-4503-9103-491b28305c2d

    async def _post_reconnaissance_records(
        self, run_id: str, plan_data: dict[str, Any]
    ) -> None:
        """Record what reconnaissance saw, and what it could not see, on the run.

        Two different absences, two different instruments, deliberately:

        - A plan was produced but reconnaissance did not run, or ran and failed
          -> ``post_unavailable``. That is a genuine "couldn't look": the run
          planned against a target it never examined, which is a human-resolvable
          state.
        - Reconnaissance ran and found no file of some governed type -> an
          ordinary report. That is a *fact about the target*, terminal and true,
          not a gap in the evidence.

        Collapsing the second into ``post_unavailable`` would stamp every one of
        them ``indeterminate`` with ``resolution_mechanism='human'`` and file it
        in the governor-adjudication backlog -- roughly fifteen rows per external
        run, each asking a human to adjudicate the fact that a target legitimately
        has no SQL migrations. The taxonomy leg exists to stop empty from reading
        as clean; it is not a general channel for absences.
        """
        if not plan_data:
            # No parse output at all -- this workflow produced no plan, so there
            # is no reconnaissance to have missed. Saying nothing is correct;
            # an "unavailable" here would invent a gap that does not exist.
            return

        recon = plan_data.get("reconnaissance")

        if not isinstance(recon, dict):
            await self.post_unavailable(
                f"goal_run.{run_id}.recon",
                reason="reconnaissance_not_recorded",
                detail={"run_id": run_id},
            )
            return

        if not recon.get("available"):
            await self.post_unavailable(
                f"goal_run.{run_id}.recon",
                reason="reconnaissance_unavailable",
                detail={"run_id": run_id, "detail": str(recon.get("reason", ""))},
            )
            return

        await self.post_report(
            f"goal_run.{run_id}.recon",
            {
                "run_id": run_id,
                "digest": recon.get("digest"),
                "observed": _blackboard_safe(recon.get("raw", {})),
            },
        )

        for item in recon.get("unavailable", []):
            if not isinstance(item, dict):
                continue
            topic = str(item.get("topic", "unspecified"))
            await self.post_report(
                f"goal_run.{run_id}.unavailable.{_subject_segment(topic)}",
                {
                    "run_id": run_id,
                    "topic": topic,
                    "reason": str(item.get("reason", "unspecified")),
                },
            )

    async def _post_decision_records(
        self, run_id: str, plan_data: dict[str, Any]
    ) -> None:
        """Put each planning decision on the run's identity as its own record.

        Numbered rather than bundled so a single decision is addressable: a
        reviewer can point at goal_run.<id>.decision.3 and a later reader can
        find exactly that one. Structured fields only -- rationale, chosen
        action, alternatives, confidence -- never chain-of-thought.
        """
        decisions = plan_data.get("decisions")
        if not isinstance(decisions, list):
            return

        for index, decision in enumerate(decisions, 1):
            if not isinstance(decision, dict):
                continue
            await self.post_report(
                f"goal_run.{run_id}.decision.{index}",
                {"run_id": run_id, "index": index, **_blackboard_safe(decision)},
            )

    async def _run_create_proposal_only(self, run_id: str) -> None:
        """ADR-160 D3, first staged conversion.

        Plans the goal directly via `PlannerAgent` (mirroring
        `ParsePhase.__init__`/`.execute()`), converts the resulting plan to
        a Proposal via `will.autonomy.plan_to_proposal.convert_execution_plan`,
        persists it in PENDING via `ProposalRepository`, and stops.
        `WorkflowOrchestrator`/`ActionExecutor` are never reached — no write
        occurs in this mode regardless of `self.write`. Approval and
        execution are a separate, later, Governor-triggered step outside
        this worker's scope.

        Every exit is either a persisted PENDING Proposal + a `post_report`
        outcome, or a refusal + a `post_observation` outcome — never a
        partial or silently-dropped result.
        """
        from will.agents.planner_agent import PlannerAgent

        try:
            planner = PlannerAgent(
                cognitive_service=self._context.cognitive_service,
                repo_path=Path(self._context.git_service.repo_path),
                qdrant_service=getattr(self._context, "qdrant_service", None),
            )
            plan = await planner.create_execution_plan(self.goal)
        except Exception as exc:
            await self._refuse_proposal_creation(
                run_id, reason="planning_failed", detail=str(exc)
            )
            return

        if not plan:
            await self._refuse_proposal_creation(
                run_id,
                reason="empty_plan",
                detail="PlannerAgent produced no executable steps for this goal.",
            )
            return

        from will.autonomy.plan_to_proposal import (
            PlanConversionRefused,
            convert_execution_plan,
        )

        try:
            scope, actions = convert_execution_plan(
                plan, workflow_type=self.workflow_type
            )
        except PlanConversionRefused as refusal:
            await self._refuse_proposal_creation(
                run_id, reason="plan_conversion_refused", detail=str(refusal)
            )
            return

        from will.autonomy.proposal import Proposal, ProposalStatus

        proposal = Proposal(
            goal=self.goal,
            actions=actions,
            scope=scope,
            status=ProposalStatus.PENDING,
            created_by="api.develop_goal",
        )
        proposal.compute_risk()

        is_valid, errors = proposal.validate()
        if not is_valid:
            await self._refuse_proposal_creation(
                run_id, reason="proposal_invalid", detail="; ".join(errors)
            )
            return

        from body.services.service_registry import service_registry
        from will.autonomy.proposal_repository import ProposalRepository

        async with service_registry.session() as session:
            repo = ProposalRepository(session)
            proposal_id = await repo.create(proposal)
            await session.commit()

        self.proposal_id = proposal_id
        self.proposal_approval_required = proposal.approval_required

        await self.post_report(
            f"goal_run.{run_id}.outcome",
            {
                "run_id": run_id,
                "ok": True,
                "mode": "create_proposal_only",
                "goal": self.goal,
                "workflow_type": self.workflow_type,
                "proposal_id": proposal_id,
                "approval_required": proposal.approval_required,
                "risk": proposal.risk.overall_risk if proposal.risk else None,
                "scope_files": scope.files,
                "action_results_correlation_key": run_id,
            },
        )

        self.result = PhaseWorkflowResult(
            ok=True,
            workflow_type=self.workflow_type,
            phase_results=[
                PhaseResult(
                    name="create_proposal",
                    ok=True,
                    data={
                        "proposal_id": proposal_id,
                        "approval_required": proposal.approval_required,
                    },
                    duration_sec=0.0,
                )
            ],
            total_duration=0.0,
        )

    # ID: 1b723894-67d2-48d4-9d20-51215c9a4456
    async def _refuse_proposal_creation(
        self, run_id: str, *, reason: str, detail: str
    ) -> None:
        """Report a create_proposal_only refusal — fail closed, never partial."""
        await self.post_observation(
            f"goal_run.{run_id}.outcome",
            {
                "run_id": run_id,
                "ok": False,
                "mode": "create_proposal_only",
                "goal": self.goal,
                "workflow_type": self.workflow_type,
                "reason": reason,
                "detail": detail,
            },
            status="abandoned",
        )
        self.result = PhaseWorkflowResult(
            ok=False,
            workflow_type=self.workflow_type,
            phase_results=[
                PhaseResult(
                    name="create_proposal",
                    ok=False,
                    error=detail,
                    duration_sec=0.0,
                )
            ],
            total_duration=0.0,
        )
