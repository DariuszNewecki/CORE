# src/will/governance/audit_runner.py

"""
Audit runner facade — Will-layer entry point for the /audit API
(ADR-054 D1).

The API layer must not import mind.* or shared.infrastructure.* by
constitutional rule. This module is the sanctioned bridge: it
imports the audit workflow from mind.enforcement.audit and exposes a
single async function the API can call with an injected session.

Persistence target is core.audit_run_resources (sibling table to the
legacy core.audit_runs, which remains owned by the CLI audit command
and the workflow_gate check — see migration
20260517_create_audit_run_resources.sql for why the schemas could
not be reconciled).
"""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from mind.enforcement.audit import run_audit_workflow
from mind.governance.auditor import AuditVerdict, ConstitutionalAuditor
from shared.context import CoreContext
from shared.logger import getLogger


__all__ = [
    "AuditVerdict",
    "ConstitutionalAuditor",
    "run_and_persist_audit",
]


logger = getLogger(__name__)


# ID: 045484b6-7e52-46df-b4b6-53f3e7a0de65
async def run_and_persist_audit(
    context: CoreContext,
    session: AsyncSession,
    run_id: UUID | None = None,
) -> dict:
    """Run the constitutional audit and persist the result.

    When `run_id` is None, a fresh row is INSERTed (status='pending'
    placeholder is written and overwritten with the final verdict in
    the same call). When `run_id` is supplied, the existing row — the
    pending row the API route pre-inserted so it could return the id
    to the caller with 202 — is UPDATEd in place.

    Returns:
        dict with run_id (str), verdict, finding_count, blocking_count,
        status. The shape is what /audit/runs and /audit/runs/{id}
        callers expect.
    """
    if run_id is None:
        result = await session.execute(
            text(
                """
                INSERT INTO core.audit_run_resources
                    (verdict, finding_count, blocking_count, status)
                VALUES ('pending', 0, 0, 'pending')
                RETURNING run_id
                """
            )
        )
        run_id = result.scalar_one()
        await session.commit()
        logger.info("audit_runner: inserted pending run %s", run_id)

    try:
        passed, findings = await run_audit_workflow(context)
    except Exception:
        logger.exception("audit_runner: run_audit_workflow raised for %s", run_id)
        await session.execute(
            text(
                """
                UPDATE core.audit_run_resources
                   SET status = 'failed',
                       completed_at = now()
                 WHERE run_id = :rid
                """
            ),
            {"rid": run_id},
        )
        await session.commit()
        raise

    verdict = AuditVerdict.PASS if passed else AuditVerdict.FAIL
    finding_count = len(findings)
    blocking_count = sum(1 for f in findings if f.severity.is_blocking)

    await session.execute(
        text(
            """
            UPDATE core.audit_run_resources
               SET verdict = :verdict,
                   finding_count = :finding_count,
                   blocking_count = :blocking_count,
                   status = 'completed',
                   completed_at = now()
             WHERE run_id = :rid
            """
        ),
        {
            "verdict": verdict.value,
            "finding_count": finding_count,
            "blocking_count": blocking_count,
            "rid": run_id,
        },
    )
    await session.commit()

    logger.info(
        "audit_runner: %s completed verdict=%s findings=%d blocking=%d",
        run_id,
        verdict.value,
        finding_count,
        blocking_count,
    )

    return {
        "run_id": str(run_id),
        "verdict": verdict.value,
        "finding_count": finding_count,
        "blocking_count": blocking_count,
        "status": "completed",
    }
