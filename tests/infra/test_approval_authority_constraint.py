"""Tests for the approval_authority CHECK constraint on core.autonomous_proposals.

Validates the structural half of URS NFR.5: post-cutoff rows must carry a
non-NULL approval_authority when status is in the approved-family; pre-cutoff
rows are admitted via the carve-out (ADR-015 D7).
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import pytest
from sqlalchemy import delete, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)


_INSERT_SQL = text(
    """
    INSERT INTO core.autonomous_proposals (
        id, proposal_id, goal, status, actions, scope, risk,
        created_at, created_by, validation_checks, validation_results,
        execution_results, constitutional_constraints, approval_required,
        approved_by, approved_at, approval_authority, version, updated_at
    ) VALUES (
        gen_random_uuid(), :proposal_id, 'check constraint test', 'approved',
        '[]'::jsonb, '{}'::jsonb, NULL,
        :created_at, 'test', '[]'::jsonb, '{}'::jsonb,
        '{}'::jsonb, '{}'::jsonb, false,
        NULL, NULL, NULL, 0, now()
    )
    """
)


async def _delete(db_session: AsyncSession, proposal_id: str) -> None:
    await db_session.rollback()
    await db_session.execute(
        delete(AutonomousProposal).where(
            AutonomousProposal.proposal_id == proposal_id
        )
    )
    await db_session.commit()


async def test_constraint_rejects_post_cutoff_null_authority(
    db_session: AsyncSession,
) -> None:
    """Case D: post-cutoff row with status=approved + authority=NULL is rejected."""
    proposal_id = f"test-constraint-D-{uuid.uuid4().hex[:8]}"
    try:
        with pytest.raises(IntegrityError):
            await db_session.execute(
                _INSERT_SQL,
                {"proposal_id": proposal_id, "created_at": datetime.now(UTC)},
            )
            await db_session.commit()
    finally:
        await _delete(db_session, proposal_id)


async def test_constraint_admits_pre_cutoff_null_authority(
    db_session: AsyncSession,
) -> None:
    """Case E: pre-cutoff row with status=approved + authority=NULL is admitted (carve-out)."""
    proposal_id = f"test-constraint-E-{uuid.uuid4().hex[:8]}"
    pre_cutoff = datetime(2026, 4, 26, 12, 0, 0, tzinfo=UTC)
    try:
        await db_session.execute(
            _INSERT_SQL,
            {"proposal_id": proposal_id, "created_at": pre_cutoff},
        )
        await db_session.commit()

        result = await db_session.execute(
            text(
                "SELECT status, approval_authority FROM core.autonomous_proposals "
                "WHERE proposal_id = :pid"
            ),
            {"pid": proposal_id},
        )
        row = result.first()
        assert row is not None
        assert row.status == "approved"
        assert row.approval_authority is None
    finally:
        await _delete(db_session, proposal_id)
