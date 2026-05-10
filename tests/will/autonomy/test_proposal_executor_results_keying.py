"""Tests for the action_results keying scheme in ProposalExecutor (issue #275).

When a proposal contains N actions with the same action_id, the executor
keys ``action_results`` by ``f"{action_id}:{order}"``. This test exercises
the persistence path with a synthetic 3-step ``action_results`` dict and
asserts that all three entries survive the round-trip — guarding against
regression to the prior scheme that keyed by ``action_id`` alone and lost
N-1 results to last-write collision.

The keying expression itself lives at four sites in
``src/will/autonomy/proposal_executor.py``; this test guards the
persistence schema rather than the inline expression. Source review
remains the authoritative check on the executor's keying behavior.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from will.autonomy.proposal_state_manager import ProposalStateManager


def _draft_row(proposal_id: str) -> AutonomousProposal:
    return AutonomousProposal(
        proposal_id=proposal_id,
        goal="action_results keying unit test",
        status="draft",
        actions=[
            {"action_id": "fix.format", "parameters": {}, "order": 0},
            {"action_id": "fix.format", "parameters": {}, "order": 1},
            {"action_id": "fix.format", "parameters": {}, "order": 2},
        ],
        scope={"files": [], "modules": [], "symbols": [], "policies": []},
        constitutional_constraints={},
        approval_required=False,
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


async def test_three_same_action_id_results_persist_distinctly(
    db_session: AsyncSession,
) -> None:
    """3 fix.format steps → 3 distinct execution_results entries (#275)."""
    proposal_id = f"test-keying-{uuid.uuid4().hex[:8]}"
    db_session.add(_draft_row(proposal_id))
    await db_session.commit()

    # Mirrors the new keying scheme `f"{action_id}:{order}"` from
    # proposal_executor.py:269,305,611,622.
    results = {
        "fix.format:0": {
            "ok": True,
            "duration_sec": 0.01,
            "data": {"file": "a.py"},
            "order": 0,
            "kind": "action",
        },
        "fix.format:1": {
            "ok": True,
            "duration_sec": 0.02,
            "data": {"file": "b.py"},
            "order": 1,
            "kind": "action",
        },
        "fix.format:2": {
            "ok": False,
            "duration_sec": 0.03,
            "data": {"file": "c.py", "error": "boom"},
            "order": 2,
            "kind": "action",
        },
    }

    try:
        await ProposalStateManager(db_session).mark_completed(proposal_id, results)

        db_session.expire_all()
        row = await _fetch(db_session, proposal_id)
        assert row is not None
        stored = row.execution_results
        assert set(stored.keys()) == {"fix.format:0", "fix.format:1", "fix.format:2"}
        assert stored["fix.format:0"]["data"]["file"] == "a.py"
        assert stored["fix.format:1"]["data"]["file"] == "b.py"
        assert stored["fix.format:2"]["data"]["file"] == "c.py"
        assert stored["fix.format:0"]["order"] == 0
        assert stored["fix.format:1"]["order"] == 1
        assert stored["fix.format:2"]["order"] == 2
    finally:
        await _delete(db_session, proposal_id)
