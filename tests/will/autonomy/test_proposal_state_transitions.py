# tests/will/autonomy/test_proposal_state_transitions.py

"""Integration tests for state-predicate enforcement in ProposalStateManager (#708).

Verifies that mark_completed, mark_failed, approve, and reject all raise
ProposalNotFoundError when the proposal is not in a valid source state for
the requested transition.  Ensures that invalid transitions are silent no-ops
rather than false-success updates.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from will.autonomy.proposal_state_manager import (
    ProposalNotFoundError,
    ProposalStateManager,
)


pytestmark = [pytest.mark.integration]


def _row(proposal_id: str, *, status: str) -> AutonomousProposal:
    """Construct a minimal AutonomousProposal row in the given status."""
    return AutonomousProposal(
        proposal_id=proposal_id,
        goal="state transition guard test",
        status=status,
        actions=[{"action_id": "fix.format", "parameters": {}, "order": 0}],
        scope={"files": [], "modules": [], "symbols": [], "policies": []},
        constitutional_constraints={},
        approval_required=False,
        approval_authority="risk_classification.safe_auto_approval",
        created_at=datetime.now(UTC),
    )


async def _delete(db_session: AsyncSession, proposal_id: str) -> None:
    await db_session.rollback()
    await db_session.execute(
        delete(AutonomousProposal).where(AutonomousProposal.proposal_id == proposal_id)
    )
    await db_session.commit()


async def _fetch(db_session: AsyncSession, proposal_id: str) -> AutonomousProposal | None:
    result = await db_session.execute(
        select(AutonomousProposal).where(AutonomousProposal.proposal_id == proposal_id)
    )
    return result.scalar_one_or_none()


# ---------------------------------------------------------------------------
# mark_completed — valid source: EXECUTING only
# ---------------------------------------------------------------------------


async def test_mark_completed_from_rejected_raises(db_session: AsyncSession) -> None:
    """mark_completed on a rejected proposal raises ProposalNotFoundError (#714)."""
    proposal_id = f"test-mc-rejected-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="rejected"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).mark_completed(
                proposal_id, results={}
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "rejected"
    finally:
        await _delete(db_session, proposal_id)


async def test_mark_completed_from_approved_raises(db_session: AsyncSession) -> None:
    """mark_completed on an approved proposal raises ProposalNotFoundError (#708)."""
    proposal_id = f"test-mc-approved-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="approved"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).mark_completed(
                proposal_id, results={}
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "approved"
    finally:
        await _delete(db_session, proposal_id)


async def test_mark_completed_from_completed_raises(db_session: AsyncSession) -> None:
    """Re-completing an already-completed proposal raises ProposalNotFoundError (#708)."""
    proposal_id = f"test-mc-completed-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="completed"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).mark_completed(
                proposal_id, results={}
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "completed"
    finally:
        await _delete(db_session, proposal_id)


# ---------------------------------------------------------------------------
# mark_failed — valid source: EXECUTING only
# ---------------------------------------------------------------------------


async def test_mark_failed_from_draft_raises(db_session: AsyncSession) -> None:
    """mark_failed on a draft proposal raises ProposalNotFoundError (#708)."""
    proposal_id = f"test-mf-draft-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="draft"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).mark_failed(
                proposal_id, reason="test", results={}
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "draft"
    finally:
        await _delete(db_session, proposal_id)


async def test_mark_failed_from_completed_raises(db_session: AsyncSession) -> None:
    """mark_failed on an already-completed proposal raises ProposalNotFoundError (#708)."""
    proposal_id = f"test-mf-completed-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="completed"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).mark_failed(
                proposal_id, reason="test", results={}
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "completed"
    finally:
        await _delete(db_session, proposal_id)


# ---------------------------------------------------------------------------
# approve — valid sources: DRAFT, PENDING
# ---------------------------------------------------------------------------


async def test_approve_from_approved_raises(db_session: AsyncSession) -> None:
    """Re-approving an already-approved proposal raises ProposalNotFoundError (#714)."""
    proposal_id = f"test-app-approved-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="approved"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="cli_admin",
                approval_authority="principal.governor",
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "approved"
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_from_completed_raises(db_session: AsyncSession) -> None:
    """Approving a completed proposal raises ProposalNotFoundError (#714)."""
    proposal_id = f"test-app-completed-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="completed"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="cli_admin",
                approval_authority="principal.governor",
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "completed"
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_from_failed_raises(db_session: AsyncSession) -> None:
    """Approving a failed proposal raises ProposalNotFoundError (#714)."""
    proposal_id = f"test-app-failed-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="failed"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="cli_admin",
                approval_authority="principal.governor",
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "failed"
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_from_rejected_raises(db_session: AsyncSession) -> None:
    """Approving a rejected proposal raises ProposalNotFoundError (#714)."""
    proposal_id = f"test-app-rejected-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="rejected"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="cli_admin",
                approval_authority="principal.governor",
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "rejected"
    finally:
        await _delete(db_session, proposal_id)


async def test_approve_from_executing_raises(db_session: AsyncSession) -> None:
    """Approving an executing proposal raises ProposalNotFoundError (#714)."""
    proposal_id = f"test-app-executing-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="executing"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).approve(
                proposal_id,
                approved_by="cli_admin",
                approval_authority="principal.governor",
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "executing"
    finally:
        await _delete(db_session, proposal_id)


# ---------------------------------------------------------------------------
# reject — valid sources: DRAFT, PENDING, APPROVED
# ---------------------------------------------------------------------------


async def test_reject_from_completed_raises(db_session: AsyncSession) -> None:
    """Rejecting a completed proposal raises ProposalNotFoundError (#708)."""
    proposal_id = f"test-rej-completed-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="completed"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).reject(
                proposal_id, reason="stale"
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "completed"
    finally:
        await _delete(db_session, proposal_id)


async def test_reject_from_failed_raises(db_session: AsyncSession) -> None:
    """Rejecting an already-failed proposal raises ProposalNotFoundError (#708)."""
    proposal_id = f"test-rej-failed-{uuid.uuid4().hex[:8]}"
    db_session.add(_row(proposal_id, status="failed"))
    await db_session.commit()
    try:
        with pytest.raises(ProposalNotFoundError):
            await ProposalStateManager(db_session).reject(
                proposal_id, reason="stale"
            )
        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None and row.status == "failed"
    finally:
        await _delete(db_session, proposal_id)
