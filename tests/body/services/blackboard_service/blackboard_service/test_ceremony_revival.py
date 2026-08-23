# tests/body/services/blackboard_service/blackboard_service/test_ceremony_revival.py
"""Integration test: ceremony explicit-rejection revival (ADR-154 D3).

revive_ceremony_findings_for_rejected_proposal is the ceremony-lane
analogue of revive_delegated_findings_for_rejected_proposal — same
destination (indeterminate+human), different predicate (matches
resolution_mechanism='reaudit', a ceremony finding's birth value while
deferred, not 'human') and different Body operation (cannot reuse the
assisted-lane helper — its predicate would match zero rows against a
ceremony finding). Against a real database transaction, not mocks.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.blackboard_service import BlackboardService
from body.services.service_registry import service_registry
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
            "worker_name": f"test_ceremony_revival_{str(worker_uuid)[:8]}",
        },
    )


async def _seed_deferred_ceremony_finding(
    session: AsyncSession,
    finding_id: uuid.UUID,
    worker_uuid: uuid.UUID,
    proposal_id: str,
) -> None:
    """A ceremony finding: claimed by a real worker, deferred to a DRAFT
    proposal that has now been rejected — resolution_mechanism is 'reaudit'
    (its birth value), NOT 'human' (that's the assisted-lane shape)."""
    payload = {
        "rule": "modularity.class_too_large",
        "file_path": "src/x.py",
        "proposal_id": proposal_id,
    }
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, resolution_mechanism, claimed_by, claimed_at)
            VALUES
                (:id, :worker_uuid, 'finding', 'parse', 'deferred_to_proposal',
                 'modularity.class_too_large::src/x.py',
                 cast(:payload as jsonb), 'reaudit', :worker_uuid, now())
            """
        ),
        {
            "id": finding_id,
            "worker_uuid": worker_uuid,
            "payload": json.dumps(payload),
        },
    )
    await session.commit()


async def _finding_row(session: AsyncSession, finding_id: uuid.UUID):
    result = await session.execute(
        text(
            "SELECT status, resolution_mechanism, claimed_by, claimed_at "
            "FROM core.blackboard_entries WHERE id = :id"
        ),
        {"id": finding_id},
    )
    return result.fetchone()


async def test_ceremony_rejection_revival_lands_indeterminate_human(
    db_session: AsyncSession,
) -> None:
    """Explicit ceremony rejection -> indeterminate+human, claim cleared —
    proving the correctly-named ceremony-specific Body operation works
    against a real reaudit-mechanism finding the assisted-lane helper
    cannot touch."""
    await _ensure_blackboard_table(db_session)

    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    proposal_id = f"test-ceremony-reject-{uuid.uuid4().hex[:8]}"
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    await _seed_deferred_ceremony_finding(
        db_session, finding_id, worker_uuid, proposal_id
    )

    try:
        service = BlackboardService()
        revival = await service.revive_ceremony_findings_for_rejected_proposal(
            proposal_id=proposal_id,
            reason="governor rejected the ceremony candidate",
        )

        assert revival is not None
        assert revival["revived_count"] == 1
        assert str(finding_id) in revival["revived_finding_ids"]

        frow = await _finding_row(db_session, finding_id)
        assert frow is not None
        status, resolution_mechanism, claimed_by, claimed_at = frow
        assert status == "indeterminate"
        assert resolution_mechanism == "human"
        assert claimed_by is None
        assert claimed_at is None
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        await db_session.commit()


async def test_assisted_lane_rejection_helper_does_not_match_ceremony_finding(
    db_session: AsyncSession,
) -> None:
    """The governor's exact concern, proven empirically: the assisted-lane
    rejection helper's predicate (resolution_mechanism='human') must NOT
    match a ceremony finding (resolution_mechanism='reaudit') — calling it
    on a ceremony proposal would silently strand the finding forever."""
    await _ensure_blackboard_table(db_session)

    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    proposal_id = f"test-ceremony-wrong-helper-{uuid.uuid4().hex[:8]}"
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    await _seed_deferred_ceremony_finding(
        db_session, finding_id, worker_uuid, proposal_id
    )

    try:
        service = BlackboardService()
        revival = await service.revive_delegated_findings_for_rejected_proposal(
            proposal_id=proposal_id,
            reason="wrong helper — should match nothing",
        )
        assert revival is None, (
            "the assisted-lane helper must not match a ceremony finding — "
            "if it did, this reveals a predicate regression"
        )

        # Confirm the finding was genuinely untouched, not just that the
        # dict came back None.
        frow = await _finding_row(db_session, finding_id)
        assert frow is not None
        status, resolution_mechanism, claimed_by, _claimed_at = frow
        assert status == "deferred_to_proposal"
        assert resolution_mechanism == "reaudit"
        assert claimed_by == worker_uuid
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        await db_session.commit()


async def test_ceremony_revival_returns_none_when_nothing_matched(
    db_session: AsyncSession,
) -> None:
    await _ensure_blackboard_table(db_session)
    service = BlackboardService()
    revival = await service.revive_ceremony_findings_for_rejected_proposal(
        proposal_id="no-such-ceremony-proposal",
        reason="irrelevant",
    )
    assert revival is None
