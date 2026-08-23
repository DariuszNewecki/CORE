# tests/body/services/test_proposal_submission_service.py
"""Integration tests: atomic proposal submission (ADR-154 D3b).

Proves the fault-injection properties the governor asked for, against a
real database transaction — not mocks. A mock can prove the code called
the right functions in the right order; it cannot prove Postgres actually
rolled back a half-applied transaction. These tests seed real
core.blackboard_entries rows and assert on real post-call row state.

Also the regression test for the defect this module fixes: before ADR-154
D3b, LaneService.propose_validated_diff created the Proposal in one session
(flush-only, ProposalRepository.create() never commits) and deferred the
finding in a separate, committing session — so the proposal row was
silently discarded on session close while the finding was durably stamped
deferred_to_proposal against a proposal_id that never actually existed.
test_submit_persists_proposal_and_defers_finding_atomically proves the
proposal now durably exists after a real commit.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.proposal_submission_service import (
    ProposalSubmissionError,
    submit_assisted_lane_proposal,
)
from body.services.service_registry import service_registry
from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.infrastructure.database.models.workers import BlackboardEntry
from shared.infrastructure.database.session_manager import get_session
from will.autonomy.proposal import (
    Proposal,
    ProposalAction,
    ProposalScope,
    ProposalStatus,
)


pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Match the production entry-point bootstrap so
    service_registry.session() acquires a live session against core_test
    inside the service under test."""
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
            "worker_name": f"test_submission_{str(worker_uuid)[:8]}",
        },
    )


async def _seed_delegated_finding(
    session: AsyncSession,
    finding_id: uuid.UUID,
    worker_uuid: uuid.UUID,
    *,
    status: str = "indeterminate",
    resolution_mechanism: str | None = "human",
) -> None:
    """Seed a blackboard finding. Defaults to the eligible assisted-lane
    shape (indeterminate + human); pass a different status/mechanism to
    seed an ineligible row for the rollback tests."""
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, resolution_mechanism)
            VALUES
                (:id, :worker_uuid, 'finding', 'parse', :status,
                 'purity.no_orphan_files::src/x.py',
                 cast(:payload as jsonb), :resolution_mechanism)
            """
        ),
        {
            "id": finding_id,
            "worker_uuid": worker_uuid,
            "status": status,
            "resolution_mechanism": resolution_mechanism,
            "payload": json.dumps(
                {"rule": "purity.no_orphan_files", "file_path": "src/x.py"}
            ),
        },
    )
    await session.commit()


def _draft_proposal() -> Proposal:
    return Proposal(
        goal="ADR-154 D3b atomic submission regression test",
        actions=[
            ProposalAction(
                action_id="assisted.apply_diff",
                parameters={"patch": "--- a/x\n+++ b/x\n", "write": True},
                order=0,
            )
        ],
        scope=ProposalScope(files=["src/x.py"]),
        status=ProposalStatus.DRAFT,
        created_by="test-atomic-submission",
        validation_checks=["assisted.validate_diff"],
        validation_results={"assisted.validate_diff": True},
        approval_required=True,
        constitutional_constraints={"assisted_lane": True},
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
            "SELECT status, payload->>'proposal_id' FROM core.blackboard_entries "
            "WHERE id = :id"
        ),
        {"id": finding_id},
    )
    return result.fetchone()


async def test_submit_persists_proposal_and_defers_finding_atomically(
    db_session: AsyncSession,
) -> None:
    """The regression test: before this module, the proposal was silently
    never committed. Here it must durably exist after a fresh session reads
    it back, and the finding must be deferred and pointing at it."""
    await _ensure_blackboard_table(db_session)

    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    await _seed_delegated_finding(db_session, finding_id, worker_uuid)

    proposal = _draft_proposal()
    try:
        proposal_id = await submit_assisted_lane_proposal(
            proposal, finding_ids=[str(finding_id)]
        )
        assert proposal_id == proposal.proposal_id

        # Read back through a FRESH session — proves durability, not just
        # in-transaction visibility.
        async with service_registry.session() as fresh:
            assert await _proposal_row_exists(fresh, proposal_id) is True
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            assert frow[0] == "deferred_to_proposal"
            assert frow[1] == proposal_id
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


async def test_submit_rolls_back_proposal_when_finding_ineligible(
    db_session: AsyncSession,
) -> None:
    """A finding that is no longer indeterminate+human (already resolved,
    claimed by another proposal, whatever) makes the whole submission fail
    — including the proposal, which must not exist afterward. This is the
    "no split state" property: a failed deferral must not leave an orphan
    proposal row behind."""
    await _ensure_blackboard_table(db_session)

    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    # Ineligible: already resolved, not a live delegated lane item.
    await _seed_delegated_finding(
        db_session,
        finding_id,
        worker_uuid,
        status="resolved",
        resolution_mechanism="human",
    )

    proposal = _draft_proposal()
    try:
        with pytest.raises(ProposalSubmissionError, match="no longer eligible"):
            await submit_assisted_lane_proposal(proposal, finding_ids=[str(finding_id)])

        async with service_registry.session() as fresh:
            assert await _proposal_row_exists(fresh, proposal.proposal_id) is False
            frow = await _finding_row(fresh, finding_id)
            assert frow is not None
            assert frow[0] == "resolved", "ineligible finding must be untouched"
            assert frow[1] is None, "no proposal_id should be written"
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


async def test_submit_is_all_or_nothing_across_multiple_findings(
    db_session: AsyncSession,
) -> None:
    """N-finding submission: one eligible finding must NOT be deferred if
    a sibling finding in the same submission is ineligible — the whole
    transaction rolls back, including the already-matched row."""
    await _ensure_blackboard_table(db_session)

    eligible_id = uuid.uuid4()
    ineligible_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    await _seed_delegated_finding(db_session, eligible_id, worker_uuid)
    await _seed_delegated_finding(
        db_session,
        ineligible_id,
        worker_uuid,
        status="deferred_to_proposal",
        resolution_mechanism="human",
    )

    proposal = _draft_proposal()
    try:
        with pytest.raises(ProposalSubmissionError):
            await submit_assisted_lane_proposal(
                proposal, finding_ids=[str(eligible_id), str(ineligible_id)]
            )

        async with service_registry.session() as fresh:
            assert await _proposal_row_exists(fresh, proposal.proposal_id) is False
            erow = await _finding_row(fresh, eligible_id)
            assert erow is not None
            assert erow[0] == "indeterminate", (
                "the OTHERWISE-eligible finding must also roll back — "
                "all-or-nothing, not best-effort"
            )
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = ANY(:ids)"),
            {"ids": [eligible_id, ineligible_id]},
        )
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal.proposal_id
            )
        )
        await db_session.commit()


async def test_submit_rejects_empty_finding_ids_without_touching_db() -> None:
    """No finding_ids is a caller error, not a zero-row no-op — a proposal
    with nothing to defer to should never be silently created."""
    with pytest.raises(ProposalSubmissionError, match="at least one finding_id"):
        await submit_assisted_lane_proposal(_draft_proposal(), finding_ids=[])
