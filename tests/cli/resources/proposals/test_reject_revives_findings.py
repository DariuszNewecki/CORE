"""Integration test: CLI reject_proposal revives deferred findings (#286).

Before this fix, `core-admin proposals reject` only flipped the proposal
row's status; findings parked at `deferred_to_proposal` for that proposal
stranded permanently. The audit sensor would re-emit fresh findings for
the underlying violation, but the original deferred entries became
unreachable — broken consequence chain.

The fix mirrors the ProposalConsumerWorker failure path: after the state
transition, the CLI invokes
`BlackboardService.revive_findings_for_failed_proposal` so deferred
findings flip back to the active set with claimed_by/claimed_at/resolved_at
cleared. The §7a revival report (worker-attribution per ADR-011) is
omitted on the CLI path — operator attribution lives in the proposal
row's failure_reason and rejected status, mirroring how
`approve_proposal` posts no report either.

Per ADR-045 the revival target is 'awaiting_reaudit', not 'open'. The
audit sensor adjudicates each row on its next cycle and either releases
it to 'open' (violation still holds) or resolves it (cleared). This test
asserts the post-revival landing state — downstream re-evaluation is
covered by the sensor's own tests.

This test reproduces the exact two-call sequence from the patched
`reject_proposal` handler (state_manager.reject + bb_service revival)
against a synthetic deferred finding and asserts the end state.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.service_registry import service_registry
from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from shared.infrastructure.database.models.workers import BlackboardEntry
from shared.infrastructure.database.session_manager import get_session
from will.autonomy.proposal_state_manager import ProposalStateManager


pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Match the production entry-point bootstrap so
    service_registry.get_blackboard_service() acquires a live session
    against core_test inside the test."""
    service_registry.prime(get_session)


async def _ensure_blackboard_table(session: AsyncSession) -> None:
    """Create core.blackboard_entries if it is missing in the test DB.

    The live test DB enforces an FK on worker_uuid → worker_registry
    plus a CHECK on resolution_mechanism per ADR-091 D2 Revision B. Both
    constraints exist regardless of what create_all reproduces; seed
    helpers below cover the FK side.
    """
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
    """Seed a worker_registry row so blackboard_entries.worker_uuid FK is satisfied."""
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
            "worker_name": f"test_reject_revives_{str(worker_uuid)[:8]}",
        },
    )


def _approved_proposal(proposal_id: str) -> AutonomousProposal:
    """A proposal in 'approved' status — the typical state at which a
    governor would issue a manual reject."""
    return AutonomousProposal(
        proposal_id=proposal_id,
        goal="reject-revival regression test",
        status="approved",
        actions=[
            {
                "action_id": "fix.format",
                "parameters": {"write": True, "file_path": "src/foo.py"},
                "order": 0,
            }
        ],
        scope={"files": ["src/foo.py"]},
        constitutional_constraints={},
        approval_required=False,
        created_at=datetime.now(UTC),
        approved_by="test-approver",
        approved_at=datetime.now(UTC),
        approval_authority="principal.governor",
    )


async def test_reject_proposal_revives_deferred_findings(
    db_session: AsyncSession,
) -> None:
    """Mirrors the patched reject_proposal handler: state transition to
    'rejected' followed by BlackboardService revival. After the sequence,
    the deferred finding is at 'awaiting_reaudit' (ADR-045) with
    claim/resolve markers cleared, and the proposal carries the
    operator's --reason in failure_reason.
    """
    await _ensure_blackboard_table(db_session)

    proposal_id = f"test-reject-{uuid.uuid4().hex[:8]}"
    finding_id = uuid.uuid4()
    synthetic_worker_uuid = uuid.uuid4()
    payload = {
        "file_path": "src/foo.py",
        "check_id": "workflow.ruff_format_check",
        "rule": "workflow.ruff_format_check",
        "proposal_id": proposal_id,
    }

    # Seed: an approved proposal + a deferred finding whose payload
    # carries this proposal's id (mirrors the §7 transition done by
    # ViolationRemediatorWorker._defer_to_proposal).
    db_session.add(_approved_proposal(proposal_id))
    await _ensure_worker_registry_row(db_session, synthetic_worker_uuid)
    await db_session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, resolution_mechanism,
                 claimed_by, claimed_at, resolved_at)
            VALUES
                (:id, :worker_uuid, 'finding', 'parse', 'deferred_to_proposal',
                 'audit.violation::workflow.ruff_format_check',
                 cast(:payload as jsonb), 'reaudit',
                 :worker_uuid, now(), now())
            """
        ),
        {
            "id": finding_id,
            "worker_uuid": synthetic_worker_uuid,
            "payload": json.dumps(payload),
        },
    )
    await db_session.commit()

    try:
        # Mirror the reject_proposal handler's two-call sequence verbatim.
        operator_reason = "test override — reject + revive"
        async with service_registry.session() as session:
            await ProposalStateManager(session).reject(
                proposal_id, reason=operator_reason
            )

        bb_service = await service_registry.get_blackboard_service()
        revival = await bb_service.revive_findings_for_failed_proposal(
            proposal_id=proposal_id,
            failure_reason=f"rejected by CLI operator: {operator_reason}",
        )

        # Revival summary: one finding flipped.
        assert revival is not None, "revival returned None — finding not found"
        assert revival["revived_count"] == 1
        assert str(finding_id) in revival["revived_finding_ids"]
        assert "rejected by CLI operator" in revival["failure_reason"]

        # Proposal row reflects the rejection.
        db_session.expire_all()
        proposal_row = await db_session.execute(
            text(
                "SELECT status, failure_reason FROM core.autonomous_proposals "
                "WHERE proposal_id = :pid"
            ),
            {"pid": proposal_id},
        )
        prow = proposal_row.fetchone()
        assert prow is not None
        assert prow[0] == "rejected"
        assert operator_reason in prow[1]

        # Finding row is now at awaiting_reaudit (ADR-045), with
        # claim/resolve markers cleared per
        # BlackboardService.revive_findings_for_failed_proposal contract.
        # The audit sensor adjudicates the row on its next cycle.
        finding_row = await db_session.execute(
            text(
                "SELECT status, claimed_by, claimed_at, resolved_at "
                "FROM core.blackboard_entries WHERE id = :id"
            ),
            {"id": finding_id},
        )
        frow = finding_row.fetchone()
        assert frow is not None
        assert frow[0] == "awaiting_reaudit", (
            f"finding status={frow[0]!r}, "
            "expected 'awaiting_reaudit' after revival (ADR-045)"
        )
        assert frow[1] is None, "claimed_by should be cleared on revival"
        assert frow[2] is None, "claimed_at should be cleared on revival"
        assert frow[3] is None, "resolved_at should be cleared on revival"
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        await db_session.commit()


async def test_reject_proposal_revival_returns_none_when_no_deferred_findings(
    db_session: AsyncSession,
) -> None:
    """If a proposal had no findings deferred to it (e.g. a proposal
    created by paths other than ViolationRemediatorWorker), revival
    returns None and the operator sees no extra revival line — the
    reject is still recorded normally.
    """
    await _ensure_blackboard_table(db_session)

    proposal_id = f"test-reject-empty-{uuid.uuid4().hex[:8]}"
    db_session.add(_approved_proposal(proposal_id))
    await db_session.commit()

    try:
        async with service_registry.session() as session:
            await ProposalStateManager(session).reject(
                proposal_id, reason="no findings to revive"
            )

        bb_service = await service_registry.get_blackboard_service()
        revival = await bb_service.revive_findings_for_failed_proposal(
            proposal_id=proposal_id,
            failure_reason="rejected by CLI operator: no findings to revive",
        )

        assert revival is None, (
            f"expected None when proposal had no deferred findings, got {revival!r}"
        )
    finally:
        await db_session.rollback()
        await db_session.execute(
            delete(AutonomousProposal).where(
                AutonomousProposal.proposal_id == proposal_id
            )
        )
        await db_session.commit()
