# src/will/orchestration/goal_run_records.py

"""How a goal run is recorded on the blackboard (#895 U1/U2).

Split out of GoalExecutionWorker, which had grown two responsibilities: running
a goal, and describing what the run observed. The second is the one Trial 0
scores, so it is worth being able to read on its own.

It lives under orchestration rather than workers deliberately. Anything under
``src/will/workers/`` is a worker as far as
``architecture.workers.no_direct_worker_import`` is concerned, and a worker
importing it would read as worker-to-worker coupling. This is a run-record
helper, not a worker, and its location says so.

Every function here posts under the run's identity (``goal_run.<run_id>.*``).
None of them decides anything: the distinctions they encode -- a report versus
an unavailable, a finding versus a recorded silence -- are made where the fact
originates, and are only carried faithfully here.
"""

from __future__ import annotations

import dataclasses
from typing import Any, Protocol

from pydantic import BaseModel

from shared.logger import getLogger
from shared.models.workflow_models import PhaseWorkflowResult


logger = getLogger(__name__)


# ID: 872590f0-b998-45aa-8b8a-e37cce217dea
class RunRecordPoster(Protocol):
    """The subset of Worker a run record needs: the sanctioned post methods."""

    # ID: 0f309331-d536-434b-b6ce-4c1bb250f930
    async def post_report(self, subject: str, payload: dict[str, Any]) -> Any:
        """Post a terminal report under the given subject."""
        ...

    # ID: 66da49c1-abb4-4a04-a6ce-6250c72ee364
    async def post_unavailable(
        self, subject: str, *, reason: str, detail: dict[str, Any] | None = None
    ) -> Any:
        """Post an instrument-unavailable observation -- "couldn't look"."""
        ...


# ID: a4510722-ac0e-48d0-93a9-9d6c215bc6d5
def blackboard_safe(value: Any) -> Any:
    """Return *value* with every pydantic model rendered as JSON-safe data.

    ParsePhase leaves the plan under ``data["execution_plan"]`` as
    ``list[ExecutionTask]`` -- the objects CodeGenerationPhase consumes. The
    Blackboard stores ``json.dumps(payload)``, so posting that dict raw fails
    with "Object of type ExecutionTask is not JSON serializable" on EVERY
    outcome path once a plan exists, and the run's outcome is never recorded
    (the #894 seeded live run was the first orchestrator-path run with a
    real plan to reach this line; the ADR-160 create_proposal_only path posts
    no plan). Dataclass instances are rendered via ``asdict``. Containers
    are walked; other values pass through unchanged.
    """
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        # Same bug class, second instance (2026-09-17 cold run): the
        # evaluation workflow's plan is list[InvestigationStep], a frozen
        # dataclass, and the outcome post crashed on it -- losing the run's
        # outcome record entirely, which is an I-4 failure, not just a log line.
        return blackboard_safe(dataclasses.asdict(value))
    if isinstance(value, dict):
        return {k: blackboard_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [blackboard_safe(v) for v in value]
    return value


def _subject_segment(topic: str) -> str:
    """Normalise a recon topic into a dotted blackboard subject segment.

    Topic identity ("artifact_type:infra") is preserved verbatim in the payload;
    the subject uses dots so it reads like every other subject in the system and
    dedup keys stay consistent.
    """
    return topic.replace(":", ".").replace("/", ".").replace(" ", "_")


# ID: 0fa22465-30d1-4389-a974-6c12502936c9
async def post_reconnaissance_records(
    poster: RunRecordPoster, run_id: str, plan_data: dict[str, Any]
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
        await poster.post_unavailable(
            f"goal_run.{run_id}.recon",
            reason="reconnaissance_not_recorded",
            detail={"run_id": run_id},
        )
        return

    if not recon.get("available"):
        await poster.post_unavailable(
            f"goal_run.{run_id}.recon",
            reason="reconnaissance_unavailable",
            detail={"run_id": run_id, "detail": str(recon.get("reason", ""))},
        )
        return

    await poster.post_report(
        f"goal_run.{run_id}.recon",
        {
            "run_id": run_id,
            "digest": recon.get("digest"),
            "observed": blackboard_safe(recon.get("raw", {})),
        },
    )

    for item in recon.get("unavailable", []):
        if not isinstance(item, dict):
            continue
        topic = str(item.get("topic", "unspecified"))
        await poster.post_report(
            f"goal_run.{run_id}.unavailable.{_subject_segment(topic)}",
            {
                "run_id": run_id,
                "topic": topic,
                "reason": str(item.get("reason", "unspecified")),
            },
        )


# ID: 820b5632-4bdd-4a00-a142-a17e062d6d00
async def post_decision_records(
    poster: RunRecordPoster, run_id: str, plan_data: dict[str, Any]
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
        await poster.post_report(
            f"goal_run.{run_id}.decision.{index}",
            {"run_id": run_id, "index": index, **blackboard_safe(decision)},
        )


# ID: 5bf12a42-5e75-4c62-bbcd-e9e8d444519b
async def post_finding_records(
    poster: RunRecordPoster, run_id: str, result: PhaseWorkflowResult
) -> None:
    """Put each investigation finding on the run's identity as its own record.

    Findings are evidence, so they are posted as reports rather than
    observations: an observation invites a resolution, and a finding about a
    target is not something anyone resolves. Trial 0's recall figure is
    scored over exactly these records, outside the runner.

    A run that produced an investigation but no findings posts a record
    saying so. Silence there would be indistinguishable from a run whose
    findings were lost.
    """
    runtime_data = next(
        (p.data for p in result.phase_results if p.name == "runtime"), {}
    )
    # RuntimePhase nests each sub-phase's data under its name
    # (``data["investigation"]["findings"]``); reading the flat key alone
    # found nothing and returned silently -- the 2026-09-17 cold run posted
    # neither findings nor ``findings.empty`` for a run that produced three.
    investigation = (runtime_data or {}).get("investigation")
    if isinstance(investigation, dict) and "findings" in investigation:
        runtime_data = investigation
    if "findings" not in (runtime_data or {}):
        return

    findings = runtime_data.get("findings") or []

    if not findings:
        await poster.post_report(
            f"goal_run.{run_id}.findings.empty",
            {
                "run_id": run_id,
                "steps_executed": runtime_data.get("steps_executed", 0),
                "note": "investigation ran and produced no findings",
            },
        )
        return

    for index, finding in enumerate(findings, 1):
        if not isinstance(finding, dict):
            continue
        await poster.post_report(
            f"goal_run.{run_id}.finding.{index}",
            {"run_id": run_id, "index": index, **blackboard_safe(finding)},
        )
