"""Integration test: ViolationRemediatorWorker._create_proposal records
approval_authority on the autonomous self-promote path.

URS Q2.A acceptance criterion (ADR-015 D6): a non-NULL approval_authority
on an autonomous-path approved proposal is queryable end-to-end.

Since #886 the lane's creation path is one Body-owned transaction that
also defers the source findings (ADR-154 D3b), so each case seeds a real
``claimed`` finding for the worker's own UUID — an unseeded id is, by
design, no longer a persistable proposal — and asserts the finding side of
the ledger alongside the proposal side.

TestRemediatorWorker follows the same approval pattern; landing this one
integration test proves the refactor for the family. (AutonomousProposalWorker
was retired in favor of ViolationRemediatorWorker + ProposalConsumerWorker.)
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.service_registry import service_registry
from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.infrastructure.database.session_manager import get_session
from will.workers.violation_remediator import ViolationRemediatorWorker


pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Mirror the production entry-point bootstrap so service_registry.session()
    inside the worker can acquire a live session against core_test.
    See src/body/infrastructure/bootstrap.py:52, src/cli/admin_cli.py:86, etc."""
    service_registry.prime(get_session)


async def _seed_claimed_finding(
    session: AsyncSession,
    worker_uuid: uuid.UUID,
    *,
    rule: str,
    file_path: str,
) -> dict:
    """Seed one finding already ``claimed`` by *worker_uuid* (the state
    ``claim_findings_by_patterns`` leaves it in) and return the dict shape
    the worker hands ``_create_proposal``."""
    await session.execute(
        text(
            """
            INSERT INTO core.worker_registry
                (worker_uuid, worker_name, worker_class, phase)
            VALUES (:worker_uuid, 'test_violation_remediator', 'acting', 'remediation')
            ON CONFLICT (worker_uuid) DO NOTHING
            """
        ),
        {"worker_uuid": worker_uuid},
    )
    finding_id = uuid.uuid4()
    payload = {"file_path": file_path, "check_id": rule, "rule": rule}
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, resolution_mechanism, claimed_by, claimed_at)
            VALUES
                (:id, :worker_uuid, 'finding', 'audit', 'claimed',
                 :subject, cast(:payload as jsonb), 'reaudit',
                 :worker_uuid, now())
            """
        ),
        {
            "id": finding_id,
            "worker_uuid": worker_uuid,
            "subject": f"python::{rule}::{file_path}",
            "payload": json.dumps(payload),
        },
    )
    await session.commit()
    return {"id": str(finding_id), "payload": payload}


async def _finding_status_and_link(session: AsyncSession, finding_id: str):
    result = await session.execute(
        text(
            "SELECT status, payload->>'proposal_id' FROM core.blackboard_entries "
            "WHERE id = :id"
        ),
        {"id": uuid.UUID(finding_id)},
    )
    return result.fetchone()


async def _cleanup(session: AsyncSession, finding_id: str, proposal_id: str) -> None:
    await session.rollback()
    await session.execute(
        delete(AutonomousProposal).where(AutonomousProposal.proposal_id == proposal_id)
    )
    await session.execute(
        text("DELETE FROM core.blackboard_entries WHERE id = :id"),
        {"id": uuid.UUID(finding_id)},
    )
    await session.commit()


async def test_worker_persists_with_authority(db_session: AsyncSession) -> None:
    """Case F: a safe-risk proposal created by ViolationRemediatorWorker
    lands with status=approved, approved_by=autonomous_self_promote,
    approval_authority=risk_classification.safe_auto_approval — and its
    source finding is deferred to it in the same transaction.
    """
    worker = ViolationRemediatorWorker(declaration_name="violation_remediator")
    finding = await _seed_claimed_finding(
        db_session,
        worker._worker_uuid,
        rule="workflow.ruff_format_check",
        file_path=f"src/test_fixture_for_band_b_{uuid.uuid4().hex[:8]}.py",
    )

    submission = await worker._create_proposal("fix.format", "action", [finding])
    assert submission is not None, (
        "_create_proposal returned None — proposal was not persisted"
    )
    assert submission.auto_approved is True
    assert submission.deferred_count == 1
    proposal_id = submission.proposal_id

    try:
        db_session.expire_all()
        result = await db_session.execute(
            select(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        row = result.scalar_one()
        assert row.status == "approved"
        assert row.approved_by == "autonomous_self_promote"
        assert row.approval_authority == "risk_classification.safe_auto_approval"
        assert row.approved_at is not None

        frow = await _finding_status_and_link(db_session, finding["id"])
        assert frow == ("deferred_to_proposal", proposal_id)
    finally:
        await _cleanup(db_session, finding["id"], proposal_id)


async def test_worker_preserves_draft_when_action_outside_safe_auto_approval_envelope(
    db_session: AsyncSession,
) -> None:
    """#853 governor ruling 6, real end-to-end: check.imports is
    impact_level: safe (so proposal.approval_required is False and the
    worker attempts safe auto-approval) but is NOT in the five-action
    safe_auto_approval_envelope. The denial must not be treated as a
    persistence failure -- the proposal must still be created and land in
    DRAFT for principal.governor review, not disappear or roll back — and
    (#886) its finding must still be deferred to it."""
    worker = ViolationRemediatorWorker(declaration_name="violation_remediator")
    finding = await _seed_claimed_finding(
        db_session,
        worker._worker_uuid,
        rule="code.imports.must_resolve",
        file_path=f"src/test_fixture_for_band_b_envelope_{uuid.uuid4().hex[:8]}.py",
    )

    submission = await worker._create_proposal("check.imports", "action", [finding])
    assert submission is not None, (
        "envelope denial must not be treated as a persistence failure -- "
        "the proposal row must still be committed"
    )
    assert submission.auto_approved is False
    proposal_id = submission.proposal_id

    try:
        db_session.expire_all()
        result = await db_session.execute(
            select(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        row = result.scalar_one()
        assert row.status == "draft"
        assert row.approved_by is None
        assert row.approval_authority is None

        frow = await _finding_status_and_link(db_session, finding["id"])
        assert frow == ("deferred_to_proposal", proposal_id)
    finally:
        await _cleanup(db_session, finding["id"], proposal_id)
