"""Integration test: ViolationRemediatorWorker._create_proposal populates
constitutional_constraints['finding_ids'] with the blackboard entry IDs of
the consumed findings.

The proposal→finding read path at
src/will/autonomy/proposal_executor.py:265-266 reads this key when emitting
consequence-log entries; without it the consequence log loses the linkage
back to the originating findings. ADR-015 D7: forward-only, no historical
backfill — this test exists to prevent regression on the new path.

Since #886 the creation path atomically defers the cited findings (ADR-154
D3b), so the two findings are seeded as real ``claimed`` rows for the
worker's UUID and the test also checks that ``finding_ids`` is exactly the
set that was deferred.
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
    session: AsyncSession, worker_uuid: uuid.UUID, *, file_path: str
) -> dict:
    rule = "workflow.ruff_format_check"
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


async def test_create_proposal_records_finding_ids(
    db_session: AsyncSession,
) -> None:
    """Two claimed findings → one proposal whose
    constitutional_constraints['finding_ids'] is a list containing the
    entry IDs of both findings (as strings), and both findings deferred.
    """
    worker = ViolationRemediatorWorker(declaration_name="violation_remediator")
    suffix = uuid.uuid4().hex[:8]
    findings = [
        await _seed_claimed_finding(
            db_session,
            worker._worker_uuid,
            file_path=f"src/test_fixture_for_finding_ids_a_{suffix}.py",
        ),
        await _seed_claimed_finding(
            db_session,
            worker._worker_uuid,
            file_path=f"src/test_fixture_for_finding_ids_b_{suffix}.py",
        ),
    ]
    finding_a_id, finding_b_id = findings[0]["id"], findings[1]["id"]

    submission = await worker._create_proposal("fix.format", "action", findings)
    assert submission is not None, (
        "_create_proposal returned None — proposal was not persisted"
    )
    assert submission.deferred_count == 2
    proposal_id = submission.proposal_id

    try:
        db_session.expire_all()
        result = await db_session.execute(
            select(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        row = result.scalar_one()

        constraints = row.constitutional_constraints
        assert "finding_ids" in constraints, (
            "constitutional_constraints missing 'finding_ids' key — "
            "the proposal→finding read path is asymmetric again"
        )
        recorded = constraints["finding_ids"]
        assert isinstance(recorded, list), (
            f"finding_ids must be a list, got {type(recorded).__name__}"
        )
        assert all(isinstance(fid, str) for fid in recorded), (
            f"finding_ids entries must all be strings, got {recorded!r}"
        )
        assert set(recorded) == {finding_a_id, finding_b_id}, (
            f"finding_ids must contain both consumed entry IDs, got {recorded!r}"
        )

        deferred = await db_session.execute(
            text(
                "SELECT id::text FROM core.blackboard_entries "
                "WHERE id = ANY(:ids) AND status = 'deferred_to_proposal' "
                "AND payload->>'proposal_id' = :pid"
            ),
            {
                "ids": [uuid.UUID(finding_a_id), uuid.UUID(finding_b_id)],
                "pid": proposal_id,
            },
        )
        assert {r[0] for r in deferred.fetchall()} == set(recorded), (
            "finding_ids must be exactly the set deferred in the same transaction"
        )
    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = ANY(:ids)"),
            {"ids": [uuid.UUID(finding_a_id), uuid.UUID(finding_b_id)]},
        )
        await db_session.commit()
