# tests/body/services/blackboard_service/blackboard_service/test_delegated_revival_claim_clearing.py
"""Integration tests: assisted-lane revival lifecycle correction
(governor decision, 2026-08-23).

Two things against a real database transaction, not mocks:

1. revive_delegated_findings_for_failed_proposal (new) — the assisted-lane
   EXECUTION-failure revival path, distinct from rejection. Lands the
   finding back at indeterminate+human, preserving the delegation, but
   never passes the ADR-104 D9 remediation-attempt cap (assisted-lane
   findings never enter that handling).
2. revive_delegated_findings_for_rejected_proposal (fixed) — its own
   docstring claimed "clear any claim" but the SQL only cleared the worker
   claimed_by/claimed_at columns, leaving payload.lane_claimed_by/
   lane_claimed_at (the external-agent claim marker
   claim_delegated_finding stamps) untouched. Both tests here prove the
   agent-claim payload keys are actually removed.
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
            "worker_name": f"test_delegated_revival_{str(worker_uuid)[:8]}",
        },
    )


async def _seed_claimed_deferred_finding(
    session: AsyncSession,
    finding_id: uuid.UUID,
    worker_uuid: uuid.UUID,
    proposal_id: str,
) -> None:
    """A delegated finding an agent claimed, then got deferred to a
    proposal that has now either failed or been rejected — the exact
    state both revival paths under test must repair."""
    payload = {
        "rule": "purity.no_orphan_files",
        "file_path": "src/x.py",
        "proposal_id": proposal_id,
        "lane_claimed_by": "claude-code",
        "lane_claimed_at": "2026-08-23T12:00:00+00:00",
    }
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, resolution_mechanism, claimed_by, claimed_at)
            VALUES
                (:id, :worker_uuid, 'finding', 'parse', 'deferred_to_proposal',
                 'purity.no_orphan_files::src/x.py',
                 cast(:payload as jsonb), 'human', :worker_uuid, now())
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
            "SELECT status, resolution_mechanism, claimed_by, claimed_at, payload "
            "FROM core.blackboard_entries WHERE id = :id"
        ),
        {"id": finding_id},
    )
    return result.fetchone()


async def test_execution_failure_revival_lands_indeterminate_human_and_clears_claim(
    db_session: AsyncSession,
) -> None:
    """1. status -> indeterminate+human. 2. both claim surfaces cleared."""
    await _ensure_blackboard_table(db_session)

    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    proposal_id = f"test-exec-fail-{uuid.uuid4().hex[:8]}"
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    await _seed_claimed_deferred_finding(
        db_session, finding_id, worker_uuid, proposal_id
    )

    try:
        service = BlackboardService()
        revival = await service.revive_delegated_findings_for_failed_proposal(
            proposal_id=proposal_id,
            failure_reason="assisted.apply_diff failed: base-SHA mismatch",
        )

        assert revival is not None
        assert revival["revived_count"] == 1
        assert revival["proposal_id"] == proposal_id
        assert (
            revival["failure_reason"] == "assisted.apply_diff failed: base-SHA mismatch"
        )
        assert str(finding_id) in revival["revived_finding_ids"]
        # 4. this dict shape has no remediation-cap keys at all — there is
        # no cap machinery in this path for a caller to accidentally invoke.
        assert "abandoned_finding_ids" not in revival
        assert "abandoned_count" not in revival

        frow = await _finding_row(db_session, finding_id)
        assert frow is not None
        status, resolution_mechanism, claimed_by, claimed_at, payload = frow
        assert status == "indeterminate"
        assert resolution_mechanism == "human"
        assert claimed_by is None
        assert claimed_at is None
        assert "lane_claimed_by" not in payload
        assert "lane_claimed_at" not in payload
        # The delegation itself survives — proposal_id linkage from the
        # failed attempt is left as-is (last-writer-wins on the next defer).
        assert payload["proposal_id"] == proposal_id
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        await db_session.commit()


async def test_execution_failure_revival_returns_none_when_nothing_matched(
    db_session: AsyncSession,
) -> None:
    await _ensure_blackboard_table(db_session)
    service = BlackboardService()
    revival = await service.revive_delegated_findings_for_failed_proposal(
        proposal_id="no-such-proposal",
        failure_reason="irrelevant",
    )
    assert revival is None


async def test_rejection_revival_also_clears_the_agent_claim(
    db_session: AsyncSession,
) -> None:
    """6. Governor rejection still lands at indeterminate+human AND now
    also clears the stale agent-claim payload keys (the drift fix)."""
    await _ensure_blackboard_table(db_session)

    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    proposal_id = f"test-reject-claim-{uuid.uuid4().hex[:8]}"
    await _ensure_worker_registry_row(db_session, worker_uuid)
    await db_session.commit()
    await _seed_claimed_deferred_finding(
        db_session, finding_id, worker_uuid, proposal_id
    )

    try:
        service = BlackboardService()
        revival = await service.revive_delegated_findings_for_rejected_proposal(
            proposal_id=proposal_id,
            reason="governor rejected the candidate diff",
        )

        assert revival is not None
        assert revival["revived_count"] == 1

        frow = await _finding_row(db_session, finding_id)
        assert frow is not None
        status, resolution_mechanism, claimed_by, claimed_at, payload = frow
        assert status == "indeterminate"
        assert resolution_mechanism == "human"
        assert claimed_by is None
        assert claimed_at is None
        assert "lane_claimed_by" not in payload, (
            "drift fix: rejection revival must clear the agent claim, not "
            "just the worker claimed_by/claimed_at columns"
        )
        assert "lane_claimed_at" not in payload
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        await db_session.commit()
