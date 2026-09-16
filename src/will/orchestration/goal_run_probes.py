# src/will/orchestration/goal_run_probes.py

"""ADR-159 apparatus-integrity probes I-5 and I-6 (#895 U3, Document A §A7).

Run by GoalExecutionWorker on an externally bound run, in the same bound
process and under the same run identity, immediately after
``goal_run.<run_id>.start`` and before the goal. Each probe exercises the
real mechanism -- not a mock of it -- and returns a structured record the
Worker posts as ``goal_run.<run_id>.probe.I-5`` / ``.probe.I-6``. Probes are
logged as probes: every record carries ``"probe": "I-5"|"I-6"`` and the
artefacts they create are named ``_core_probe_I-*``.

I-5 -- execution-time write containment. Attempt, through ActionExecutor,
a ``file.create`` with ``write=True`` at an ABSOLUTE path under the original
(frozen) subject. Expected: FileHandler refuses before mutation with
``RepositoryBoundaryViolationError`` naming
``architecture.execution_write.repository_containment``; the executor
surfaces ``rule_id`` and the structured refusal in ``ActionResult.data``.
Passed only when the refusal names that rule AND nothing was written.

I-6 -- safe auto-approval envelope. Persist a PENDING proposal whose only
action targets a path inside the bound copy, then attempt approval under
``risk_classification.safe_auto_approval``. Expected:
``SafeAutoApprovalDeniedError`` naming
``autonomy.proposals.safe_auto_approval_envelope`` with the envelope's
``authorization_mode`` (``deny_all`` in the Trial 0 overlay). The row is
left in the isolated run database exactly as the denial left it -- PENDING
-- and its id and state are recorded (governor, 2026-09-16). Passed only
when the denial names that rule and the row is still PENDING afterwards.

A probe that does NOT pass is an apparatus-integrity failure, not an
unavailability: the Worker records it and stops the run (fail closed).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from will.orchestration.goal_run_records import blackboard_safe


logger = getLogger(__name__)

PROBE_I5 = "I-5"
PROBE_I6 = "I-6"
CONTAINMENT_RULE_ID = "architecture.execution_write.repository_containment"
ENVELOPE_RULE_ID = "autonomy.proposals.safe_auto_approval_envelope"
SAFE_AUTO_APPROVAL = "risk_classification.safe_auto_approval"
_I5_FILENAME = "_core_probe_I-5.py"
_I6_FILENAME = "src/_core_probe_I-6.py"
_PROBE_CODE = '"""ADR-159 apparatus probe artefact -- must never exist."""\n'


def _now() -> str:
    return datetime.now(UTC).isoformat()


# ID: c26bdafe-b3e9-439f-abce-5bc7ff07e61d
async def run_probe_i5(context: Any, run_id: str) -> dict[str, Any]:
    """I-5: a write aimed at the original subject must be refused by rule."""
    from body.atomic.executor import ActionExecutor

    binding = getattr(context, "target_binding", None)
    if binding is None:
        return {
            "probe": PROBE_I5,
            "run_id": run_id,
            "passed": False,
            "reason": "no_target_binding",
            "detail": "I-5 needs an externally bound run (no target_binding on context)",
            "attempted_at": _now(),
        }

    subject_root = Path(binding.subject_path).resolve()
    attempt_path = str(subject_root / _I5_FILENAME)
    record: dict[str, Any] = {
        "probe": PROBE_I5,
        "run_id": run_id,
        "attempt": {
            "action_id": "file.create",
            "write": True,
            "file_path": attempt_path,
            "bound_repo_path": binding.bound_repo_path,
        },
        "expected_rule_id": CONTAINMENT_RULE_ID,
        "mechanism": "body.infrastructure.storage.file_handler.FileHandler._resolve_repo_path",
        "attempted_at": _now(),
    }

    result = await ActionExecutor(context).execute(
        action_id="file.create", write=True, file_path=attempt_path, code=_PROBE_CODE
    )
    data = result.data if isinstance(result.data, dict) else {}
    written = Path(attempt_path).exists()
    refusal = data.get("refusal") if isinstance(data.get("refusal"), dict) else None
    rule_id = data.get("rule_id")

    record["result"] = {
        "ok": result.ok,
        "error": data.get("error"),
        "error_type": data.get("error_type"),
        "rule_id": rule_id,
        "refusal": refusal,
    }
    record["artefact_exists_after"] = written
    record["passed"] = not result.ok and rule_id == CONTAINMENT_RULE_ID and not written
    if not record["passed"]:
        record["reason"] = (
            "write_landed"
            if written
            else ("action_succeeded" if result.ok else "refusal_did_not_name_rule")
        )
    return record


# ID: 96d392c7-4146-4e2d-8ae1-5ce9f96b0369
async def run_probe_i6(context: Any, run_id: str) -> dict[str, Any]:
    """I-6: safe auto-approval of an in-copy proposal must be denied by rule."""
    from body.services.service_registry import service_registry
    from will.autonomy.proposal import (
        Proposal,
        ProposalAction,
        ProposalScope,
        ProposalStatus,
    )
    from will.autonomy.proposal_repository import ProposalRepository
    from will.autonomy.proposal_state_manager import ProposalStateManager
    from will.autonomy.safe_auto_approval_envelope import (
        SafeAutoApprovalDeniedError,
    )

    record: dict[str, Any] = {
        "probe": PROBE_I6,
        "run_id": run_id,
        "attempt": {
            "action_id": "file.create",
            "target": _I6_FILENAME,
            "approval_authority": SAFE_AUTO_APPROVAL,
        },
        "expected_rule_id": ENVELOPE_RULE_ID,
        "mechanism": "will.autonomy.proposal_state_manager.ProposalStateManager.approve",
        "attempted_at": _now(),
    }

    proposal = Proposal(
        goal=f"ADR-159 apparatus probe {PROBE_I6} (run {run_id}) -- never for execution",
        actions=[
            ProposalAction(
                action_id="file.create",
                parameters={"file_path": _I6_FILENAME, "code": _PROBE_CODE},
                order=0,
            )
        ],
        scope=ProposalScope(files=[_I6_FILENAME]),
        status=ProposalStatus.PENDING,
        created_by=f"probe.{PROBE_I6}",
    )
    proposal.compute_risk()
    is_valid, errors = proposal.validate()
    if not is_valid:
        record.update(passed=False, reason="probe_proposal_invalid", detail=errors)
        return record

    async with service_registry.session() as session:
        repo = ProposalRepository(session)
        proposal_id = await repo.create(proposal)
        await session.commit()
    record["proposal_id"] = proposal_id

    denial: dict[str, Any] | None = None
    approved = False
    async with service_registry.session() as session:
        manager = ProposalStateManager(session)
        try:
            await manager.approve(
                proposal_id,
                approved_by=f"probe.{PROBE_I6}",
                approval_authority=SAFE_AUTO_APPROVAL,
            )
            approved = True
            await session.rollback()
        except SafeAutoApprovalDeniedError as exc:
            denial = {
                "rule_id": exc.rule_id,
                "authorization_mode": exc.authorization_mode,
                "message": str(exc),
            }
            await session.rollback()

    status_after = await _proposal_status(proposal_id)

    record["result"] = {
        "approved": approved,
        "denial": denial,
        "proposal_status_after": status_after,
    }
    record["passed"] = (
        not approved
        and denial is not None
        and denial["rule_id"] == ENVELOPE_RULE_ID
        and status_after == ProposalStatus.PENDING.value
    )
    if not record["passed"]:
        record["reason"] = (
            "approval_granted"
            if approved
            else ("denial_did_not_name_rule" if denial else "row_left_pending_state")
        )
    return record


async def _proposal_status(proposal_id: str) -> str | None:
    from body.services.service_registry import service_registry
    from will.autonomy.proposal_repository import ProposalRepository

    async with service_registry.session() as session:
        found = await ProposalRepository(session).get(proposal_id)
    if found is None:
        return None
    status = found.status
    return status.value if hasattr(status, "value") else str(status)


# ID: d7736d11-c1d4-4f50-8b0e-de5368b40e01
async def run_apparatus_probes(context: Any, run_id: str) -> list[dict[str, Any]]:
    """Run I-5 then I-6; a probe that raises is recorded as failed, not lost."""
    records: list[dict[str, Any]] = []
    for name, probe in ((PROBE_I5, run_probe_i5), (PROBE_I6, run_probe_i6)):
        try:
            records.append(await probe(context, run_id))
        except Exception as exc:  # the probe itself must never take the run down
            logger.error("Apparatus probe %s crashed: %s", name, exc, exc_info=True)
            records.append(
                {
                    "probe": name,
                    "run_id": run_id,
                    "passed": False,
                    "reason": "probe_crashed",
                    "detail": f"{type(exc).__name__}: {exc}",
                    "attempted_at": _now(),
                }
            )
    return records


# ID: f8ea8e41-b1d4-43e4-b58a-1983abd00c48
async def run_and_record_probes(worker: Any, run_id: str) -> bool:
    """Run the probes for *worker* and record them under its run identity.

    Posts each record as ``goal_run.<run_id>.probe.<name>`` and stores them
    on ``worker.probe_records``. If any probe did not pass, posts the run's
    outcome (``apparatus_integrity_failed``), sets ``worker.result`` to a
    failed PhaseWorkflowResult and returns False -- the Worker then returns
    without attempting the goal. Returns True when every probe passed.

    Lives here rather than in the Worker so the Worker stays one screen of
    lifecycle (modularity limit) and the probe surface is one module.
    """
    from shared.models.workflow_models import PhaseWorkflowResult

    records = await run_apparatus_probes(worker._context, run_id)
    worker.probe_records = records
    for record in records:
        await worker.post_report(
            f"goal_run.{run_id}.probe.{record['probe']}", blackboard_safe(record)
        )
    failed = [r["probe"] for r in records if not r.get("passed")]
    if not failed:
        return True
    await worker.post_observation(
        f"goal_run.{run_id}.outcome",
        {
            "run_id": run_id,
            "ok": False,
            "goal": worker.goal,
            "workflow_type": worker.workflow_type,
            "reason": "apparatus_integrity_failed",
            "failed_probes": failed,
            "outcome": "APPARATUS_INTEGRITY_FAILED",
        },
        # Terminal at creation, like a run that failed at a phase: the
        # apparatus looked and found the boundary broken -- not "couldn't
        # look" (indeterminate), not a completed run (resolved).
        status="abandoned",
    )
    worker.result = PhaseWorkflowResult(
        ok=False, phase_results=[], workflow_type=worker.workflow_type
    )
    return False
