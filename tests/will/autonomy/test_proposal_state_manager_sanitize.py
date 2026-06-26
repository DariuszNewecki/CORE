"""Tests for ProposalStateManager non-ASCII sanitization (issue #274).

The PostgreSQL DB is SQL_ASCII-encoded; non-ASCII characters in the JSONB
``execution_results`` payload trigger ``UntranslatableCharacterError`` on insert.
``mark_completed()`` and ``mark_failed()`` now route their payloads through
``_sanitize_payload`` before the write, replacing non-ASCII bytes with '?'.
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
from will.autonomy.proposal_state_manager import ProposalStateManager


pytestmark = [pytest.mark.integration]


def _draft_row(proposal_id: str) -> AutonomousProposal:
    # approval_authority pre-set on the draft so mark_completed's transition
    # to 'completed' satisfies the approval_authority_required_when_approved
    # CHECK; mark_failed does not require it (status='failed' is outside the
    # constraint's enforced status set).
    return AutonomousProposal(
        proposal_id=proposal_id,
        goal="sanitize() unit test",
        status="draft",
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


async def _fetch(
    db_session: AsyncSession, proposal_id: str
) -> AutonomousProposal | None:
    result = await db_session.execute(
        select(AutonomousProposal).where(AutonomousProposal.proposal_id == proposal_id)
    )
    return result.scalar_one_or_none()


async def test_mark_completed_sanitizes_non_ascii(db_session: AsyncSession) -> None:
    """em-dash in execution_results is replaced with '?', no exception raised."""
    proposal_id = f"test-sanitize-completed-{uuid.uuid4().hex[:8]}"
    db_session.add(_draft_row(proposal_id))
    await db_session.commit()

    results = {
        "fix.path_resolver": {
            "ok": True,
            "data": {
                "message": "rewrote 5 — likely string literal",
                "nested": ["alpha — beta", {"deep": "gamma — delta"}],
            },
        }
    }

    try:
        await ProposalStateManager(db_session).mark_completed(proposal_id, results)

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "completed"
        assert row.execution_completed_at is not None

        stored = row.execution_results["fix.path_resolver"]["data"]
        assert "—" not in stored["message"]
        assert "?" in stored["message"]
        assert "—" not in stored["nested"][0]
        assert "?" in stored["nested"][0]
        assert "—" not in stored["nested"][1]["deep"]
        assert "?" in stored["nested"][1]["deep"]
    finally:
        await _delete(db_session, proposal_id)


async def test_mark_failed_sanitizes_non_ascii(db_session: AsyncSession) -> None:
    """Non-ASCII in failure_reason and execution_results both sanitized."""
    proposal_id = f"test-sanitize-failed-{uuid.uuid4().hex[:8]}"
    db_session.add(_draft_row(proposal_id))
    await db_session.commit()

    reason = "validation failed — schema mismatch"
    results = {"action": {"ok": False, "error": "boundary — violation"}}

    try:
        await ProposalStateManager(db_session).mark_failed(proposal_id, reason, results)

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        assert row.status == "failed"
        assert "—" not in row.failure_reason
        assert "?" in row.failure_reason
        assert "—" not in row.execution_results["action"]["error"]
        assert "?" in row.execution_results["action"]["error"]
    finally:
        await _delete(db_session, proposal_id)
