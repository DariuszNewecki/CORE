# tests/body/services/test_proposal_submission_service_ceremony.py
"""Integration tests: ceremony atomic proposal submission (ADR-154 D3/D3b).

Proves the fault-injection properties the governor asked for, against a
real database transaction — not mocks. Mirrors
test_proposal_submission_service.py's DB-backed pattern, for the
ceremony-lane analogue submit_ceremony_proposal: canonical ``claimed``
findings with a real worker ``claimed_by`` UUID, not the assisted-lane's
``indeterminate+human`` shape, and two checks the assisted-lane predicate
has no equivalent for — worker-UUID ownership and rule-set equality.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.proposal_submission_service import (
    ProposalSubmissionError,
    submit_ceremony_proposal,
)
from body.services.service_registry import service_registry
from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.infrastructure.database.models.workers import BlackboardEntry
from shared.infrastructure.database.session_manager import get_session


pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    service_registry.prime(get_session)


async def _ensure_blackboard_table(session: AsyncSession) -> None:
    await session.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
    conn = await session.connection()
    await conn.run_sync(
        BlackboardEntry.__table__.create,  # type: ignore[attr-defined]
        checkfirst=True,
    )
    await session.commit()


async def _ensure_worker_registry_row(
    session: AsyncSession, worker_uuid: uuid.UUID
) -> None:
    await session.execute(
        text(
            """
            INSERT INTO core.worker_registry
                (worker_uuid, worker_name, worker_class, phase)
            VALUES (:worker_uuid, :worker_name, 'sensing', 'audit')
            ON CONFLICT (worker_uuid) DO NOTHING
            """
        ),
        {
            "worker_uuid": worker_uuid,
            "worker_name": f"test_ceremony_submission_{str(worker_uuid)[:8]}",
        },
    )


async def _seed_claimed_finding(
    session: AsyncSession,
    finding_id: uuid.UUID,
    worker_uuid: uuid.UUID,
    *,
    rule: str = "modularity.class_too_large",
    status: str = "claimed",
    file_path: str = "src/x.py",
) -> None:
    """Seed a canonical ceremony-shaped finding: claimed by a real worker
    UUID, resolution_mechanism='reaudit' (birth value). subject is derived
    from (rule, file_path) — vary file_path across findings in the same
    test to satisfy uq_active_finding_identity (subject, resolution_mechanism)."""
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, resolution_mechanism, claimed_by, claimed_at)
            VALUES
                (:id, :worker_uuid, 'finding', 'parse', :status,
                 :subject, cast(:payload as jsonb), 'reaudit',
                 :worker_uuid, now())
            """
        ),
        {
            "id": finding_id,
            "worker_uuid": worker_uuid,
            "status": status,
            "subject": f"{rule}::{file_path}",
            "payload": json.dumps({"rule": rule, "file_path": file_path}),
        },
    )
    await session.commit()


def _draft_proposal(rule: str = "modularity.class_too_large") -> AutonomousProposal:
    return AutonomousProposal(
        proposal_id=str(uuid.uuid4()),
        goal="ADR-154 D3 ceremony atomic submission test",
        status="draft",
        actions=[
            {
                "action_id": "assisted.apply_diff",
                "flow_id": None,
                "parameters": {"patch": "--- a/x\n+++ b/x\n", "write": True},
                "order": 0,
            }
        ],
        scope={"files": ["src/x.py"], "modules": [], "symbols": [], "policies": []},
        created_by="test-ceremony-submission",
        validation_checks=["assisted.validate_diff"],
        validation_results={"assisted.validate_diff": True},
        approval_required=True,
        constitutional_constraints={"proposal_origin": "ceremony"},
    )


async def _proposal_row_exists(session: AsyncSession, proposal_id: str) -> bool:
    result = await session.execute(
        text("SELECT 1 FROM core.autonomous_proposals WHERE proposal_id = :pid"),
        {"pid": proposal_id},
    )
    return result.fetchone() is not None


async def _finding_row(session: AsyncSession, finding_id: uuid.UUID):
    result = await session.execute(
        text(
            "SELECT status, payload->>'proposal_id', resolution_mechanism, claimed_by "
            "FROM core.blackboard_entries WHERE id = :id"
        ),
        {"id": finding_id},
    )
    return result.fetchone()


async def test_submit_one_finding_persists_proposal_and_defers_atomically(
    db_session: AsyncSession,
) -> None:
    """One canonical claimed finding -> durable DRAFT + deferred finding."""
    await _ensure_blackboard_table(db_session)

    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    await _seed_claimed_finding(db_session, finding_id, worker_uuid)

    proposal = _draft_proposal()
    try:
        proposal_id = await submit_ceremony_proposal(
            proposal,
            finding_ids=[str(finding_id)],
            expected_worker_uuid=worker_uuid,
            expected_rule_ids=["modularity.class_too_large"],
        )
        assert proposal_id == proposal.proposal_id

        async with service_registry.session() as fresh:
            assert await _proposal_row_exists(fresh, proposal_id) is True
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            status, proposal_ref, resolution_mechanism, _claimed_by = frow
            assert status == "deferred_to_proposal"
            assert proposal_ref == proposal_id
            # resolution_mechanism must NOT be touched — stays 'reaudit' so
            # an execution failure later reaches the generic ADR-038 path.
            assert resolution_mechanism == "reaudit"
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal.proposal_id
            )
        )
        await db_session.commit()


async def test_submit_n_findings_one_draft_all_deferred_atomically(
    db_session: AsyncSession,
) -> None:
    """N claimed findings -> one DRAFT + all deferred atomically."""
    await _ensure_blackboard_table(db_session)

    ids = [uuid.uuid4() for _ in range(3)]
    worker_uuid = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    for i, fid in enumerate(ids):
        await _seed_claimed_finding(
            db_session, fid, worker_uuid, file_path=f"src/x{i}.py"
        )

    proposal = _draft_proposal()
    try:
        proposal_id = await submit_ceremony_proposal(
            proposal,
            finding_ids=[str(f) for f in ids],
            expected_worker_uuid=worker_uuid,
            expected_rule_ids=["modularity.class_too_large"],
        )

        async with service_registry.session() as fresh:
            assert await _proposal_row_exists(fresh, proposal_id) is True
            for fid in ids:
                frow = await _finding_row(fresh, fid)
                assert frow is not None
                assert frow[0] == "deferred_to_proposal"
                assert frow[1] == proposal_id
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = ANY(:ids)"),
            {"ids": ids},
        )
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal.proposal_id
            )
        )
        await db_session.commit()


async def test_submit_wrong_claimed_by_aborts_everything(
    db_session: AsyncSession,
) -> None:
    """Wrong/stale claimed_by aborts everything — no proposal persisted,
    finding untouched."""
    await _ensure_blackboard_table(db_session)

    finding_id = uuid.uuid4()
    actual_worker = uuid.uuid4()
    expected_worker = uuid.uuid4()  # different from actual_worker
    await _ensure_worker_registry_row(db_session, actual_worker)
    await _ensure_worker_registry_row(db_session, expected_worker)
    await db_session.commit()
    await _seed_claimed_finding(db_session, finding_id, actual_worker)

    proposal = _draft_proposal()
    try:
        with pytest.raises(ProposalSubmissionError, match="no longer eligible"):
            await submit_ceremony_proposal(
                proposal,
                finding_ids=[str(finding_id)],
                expected_worker_uuid=expected_worker,  # wrong worker
                expected_rule_ids=["modularity.class_too_large"],
            )

        async with service_registry.session() as fresh:
            assert await _proposal_row_exists(fresh, proposal.proposal_id) is False
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            status, proposal_ref, _resolution_mechanism, claimed_by = frow
            assert status == "claimed", "untouched — still owned by actual_worker"
            assert proposal_ref is None
            assert claimed_by == actual_worker
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal.proposal_id
            )
        )
        await db_session.commit()


async def test_submit_one_stale_finding_aborts_n_finding_submission(
    db_session: AsyncSession,
) -> None:
    """One stale finding aborts N-finding submission with no proposal
    persisted — the OTHERWISE-eligible finding must also roll back."""
    await _ensure_blackboard_table(db_session)

    eligible_id = uuid.uuid4()
    stale_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    await _seed_claimed_finding(db_session, eligible_id, worker_uuid)
    # Stale: already deferred to some other (unrelated) proposal.
    await _seed_claimed_finding(
        db_session, stale_id, worker_uuid, status="deferred_to_proposal"
    )

    proposal = _draft_proposal()
    try:
        with pytest.raises(ProposalSubmissionError, match="no longer eligible"):
            await submit_ceremony_proposal(
                proposal,
                finding_ids=[str(eligible_id), str(stale_id)],
                expected_worker_uuid=worker_uuid,
                expected_rule_ids=["modularity.class_too_large"],
            )

        async with service_registry.session() as fresh:
            assert await _proposal_row_exists(fresh, proposal.proposal_id) is False
            erow = await _finding_row(fresh, eligible_id)
            assert erow is not None
            assert erow[0] == "claimed", (
                "the OTHERWISE-eligible finding must also roll back — "
                "all-or-nothing, not best-effort"
            )
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = ANY(:ids)"),
            {"ids": [eligible_id, stale_id]},
        )
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal.proposal_id
            )
        )
        await db_session.commit()


async def test_submit_rule_set_mismatch_aborts_with_no_proposal_persisted(
    db_session: AsyncSession,
) -> None:
    """The source findings' rule set must exactly match the candidate's
    validated rule set — defense-in-depth against a caller passing a
    candidate built from a different rule set than the findings it claims
    to defer."""
    await _ensure_blackboard_table(db_session)

    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    await _seed_claimed_finding(
        db_session, finding_id, worker_uuid, rule="modularity.class_too_large"
    )

    proposal = _draft_proposal()
    try:
        with pytest.raises(ProposalSubmissionError, match="rule set"):
            await submit_ceremony_proposal(
                proposal,
                finding_ids=[str(finding_id)],
                expected_worker_uuid=worker_uuid,
                expected_rule_ids=["purity.no_orphan_files"],  # wrong rule
            )

        async with service_registry.session() as fresh:
            assert await _proposal_row_exists(fresh, proposal.proposal_id) is False
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            assert frow[0] == "claimed", "rolled back despite matching claim/worker"
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal.proposal_id
            )
        )
        await db_session.commit()


async def test_submit_rejects_empty_finding_ids_without_touching_db() -> None:
    with pytest.raises(ProposalSubmissionError, match="at least one finding_id"):
        await submit_ceremony_proposal(
            _draft_proposal(),
            finding_ids=[],
            expected_worker_uuid=uuid.uuid4(),
            expected_rule_ids=["r"],
        )
