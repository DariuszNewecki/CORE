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
- Approval:         not declared — this worker never creates Proposals; the
                     field has no enforced meaning for a non-Proposal-emitting
                     worker (verified: no code reads Worker.approval_required)

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
target reconnaissance/comprehension, and the Proposal lifecycle. This worker
executes exactly what `develop_from_goal` already executed today
(CORE-internal goal, direct ActionExecutor calls) — it adds reconstructable
evidence around that existing, already-governor-gated path; it does not
change what that path is authorized to do.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.activity_logging import activity_run
from shared.logger import getLogger
from shared.models.workflow_models import PhaseWorkflowResult
from shared.workers.base import Worker
from will.orchestration.phase_registry import PhaseRegistry
from will.orchestration.workflow_orchestrator import WorkflowOrchestrator


logger = getLogger(__name__)


# ID: ed11bc55-9c7a-4a95-a953-1ce16023104a
class GoalExecutionWorker(Worker):
    """
    Acting worker. Executes exactly one goal-driven CORE workflow via
    WorkflowOrchestrator and records its lifecycle to the Blackboard.

    One instance per invocation — constructed by the caller (today, only
    `develop_from_goal`) with the goal/workflow/write bound at construction
    time, then driven through the normal `Worker.start()` lifecycle.
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
    ) -> None:
        super().__init__(repo_root=repo_root)
        self._context = context
        self.goal = goal
        self.workflow_type = workflow_type
        self.write = write
        self.task_id = task_id
        self.run_id: str | None = None
        self.result: PhaseWorkflowResult | None = None

    # ID: 44bb5768-ff92-4abf-9883-0064e6d145a2
    async def run(self) -> None:
        """Execute this Worker's one goal-driven workflow run to completion."""
        with activity_run(
            workflow_id=f"goal_execution.{self.workflow_type}",
            details={"goal": self.goal, "write": self.write, "task_id": self.task_id},
        ) as activity:
            run_id = activity.run_id
            self.run_id = run_id

            await self.post_report(
                f"goal_run.{run_id}.start",
                {
                    "run_id": run_id,
                    "goal": self.goal,
                    "workflow_type": self.workflow_type,
                    "write": self.write,
                    "task_id": self.task_id,
                    "started_at": datetime.now(UTC).isoformat(),
                    "action_results_correlation_key": run_id,
                },
            )

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

            # Warm up brain services on the CoreContext, matching the prior
            # develop_from_goal behavior for callers whose context hasn't
            # been through the strategic-audit CLI bootstrap.
            if self._context.cognitive_service is None:
                try:
                    self._context.cognitive_service = (
                        await self._context.registry.get_cognitive_service()
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not resolve cognitive_service from registry: %s", exc
                    )
            if self._context.qdrant_service is None:
                try:
                    self._context.qdrant_service = (
                        await self._context.registry.get_qdrant_service()
                    )
                except Exception as exc:
                    logger.warning(
                        "Could not resolve qdrant_service from registry: %s", exc
                    )

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

            plan_data = next(
                (p.data for p in result.phase_results if p.name == "parse"), {}
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
