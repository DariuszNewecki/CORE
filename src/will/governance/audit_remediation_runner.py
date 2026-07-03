# src/will/governance/audit_remediation_runner.py

"""
Audit-remediation runner facade — Will-layer entry point for
POST /audit/remediations (ADR-057 D4).

The /audit/remediations surface was deferred from ADR-055 Phase 2 because
its resource model belongs alongside audit_runs, not fix_runs. It runs the
AuditRemediationService against findings produced by a prior audit_runs
row, persisting the cycle on core.audit_remediation_runs.

Single entry point:

* `run_and_persist_audit_remediation` — fire-and-forget runner. The
  route handler INSERTs a pending row with status='pending', mode, and
  audit_run_id; this function transitions it through executing →
  completed | failed and writes the RemediationResult summary into the
  result jsonb.

The remediation path is guarded by the circuit breaker (ADR-038) at the
service layer — this facade does not re-implement that check.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text

from body.self_healing.remediation_models import RemediationMode
from shared.context import CoreContext
from shared.logger import getLogger
from will.self_healing.audit_remediation_service import AuditRemediationService


__all__ = [
    "MODE_ALIASES",
    "resolve_mode",
    "run_and_persist_audit_remediation",
]


logger = getLogger(__name__)


# The ADR-057 D4 wire vocabulary ('safe' | 'medium' | 'all') maps onto
# the internal RemediationMode enum. Strict alias table — unknown values
# raise at the route layer with a 422.
MODE_ALIASES: dict[str, RemediationMode] = {
    "safe": RemediationMode.SAFE_ONLY,
    "medium": RemediationMode.MEDIUM_RISK,
    "all": RemediationMode.ALL_DETERMINISTIC,
}


# ID: 9c14e8b3-2a47-4e9d-bef1-8c3d70a52f64
def resolve_mode(mode: str) -> RemediationMode:
    """Translate the ADR-057 D4 wire-format mode to RemediationMode.

    Raises ValueError on unknown input; the route handler converts that
    to a 422.
    """
    try:
        return MODE_ALIASES[mode]
    except KeyError as exc:
        raise ValueError(
            f"Unknown remediation mode: {mode!r}. "
            f"Allowed: {sorted(MODE_ALIASES.keys())}"
        ) from exc


# ID: 5d2a90fc-7b8e-49c1-a3b0-9c8a4e1f6d72
async def _update_remediation_run_status(
    session: Any,
    run_id: UUID,
    status: str,
    *,
    started: bool = False,
    finished: bool = False,
    error: str | None = None,
    result: dict | None = None,
) -> None:
    """Update an audit_remediation_runs row's lifecycle state.

    Mirrors fix_runner._update_fix_run_status. Each call commits.
    """
    sets = ["status = :status"]
    params: dict[str, Any] = {"status": status, "rid": run_id}

    if started:
        sets.append("started_at = now()")
    if finished:
        sets.append("finished_at = now()")
    if error is not None:
        sets.append("error = :err")
        params["err"] = error
    if result is not None:
        sets.append("result = cast(:result as jsonb)")
        params["result"] = json.dumps(result, default=str)

    await session.execute(
        text(
            f"UPDATE core.audit_remediation_runs SET {', '.join(sets)} WHERE id = :rid"
        ),
        params,
    )
    await session.commit()


# ID: 1f93b6e4-4c10-4e51-a72d-6e8e5c4f9013
async def run_and_persist_audit_remediation(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    mode: str,
    write: bool,
) -> None:
    """Execute autonomous audit remediation and persist on the run row.

    The row has already been INSERTed by the route handler with
    status='pending'. This function transitions it through executing →
    completed | failed.

    `mode` is the ADR-057 wire vocabulary ('safe' | 'medium' | 'all');
    `write` honours the ADR-014 dev-phase dry-run-first discipline.

    Errors are caught and recorded on the row; this function never
    raises into the background-task scheduler.
    """
    await _update_remediation_run_status(session, run_id, "executing", started=True)

    try:
        resolved_mode = resolve_mode(mode)
    except ValueError as exc:
        await _update_remediation_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=str(exc),
        )
        return

    if context.auditor_context is None:
        await _update_remediation_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error="auditor_context not available",
        )
        return

    try:
        service = AuditRemediationService(
            file_handler=context.file_service,
            auditor_context=context.auditor_context,
            repo_root=context.git_service.repo_path,
        )
        result = await service.remediate(
            mode=resolved_mode,
            write=write,
        )
    except Exception as exc:
        logger.exception("audit_remediation_runner: remediation raised for %s", run_id)
        await _update_remediation_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    summary = {
        "total_findings": result.total_findings,
        "fixes_attempted": result.fixes_attempted,
        "fixes_succeeded": result.fixes_succeeded,
        "improvement_delta": result.improvement_delta,
        "validation_passed": result.validation_passed,
        "findings_before": result.findings_before,
        "findings_after": result.findings_after,
        "duration_sec": result.duration_sec,
        "audit_input_path": result.audit_input_path,
        "remediation_output_path": result.remediation_output_path,
        "validation_audit_path": result.validation_audit_path,
    }
    ok = result.fixes_succeeded > 0 or result.fixes_attempted == 0
    await _update_remediation_run_status(
        session,
        run_id,
        "completed" if ok else "failed",
        finished=True,
        error=None if ok else "No fixes succeeded",
        result=summary,
    )

    logger.info(
        "audit_remediation_runner: %s completed mode=%s succeeded=%d/%d",
        run_id,
        mode,
        result.fixes_succeeded,
        result.fixes_attempted,
    )
