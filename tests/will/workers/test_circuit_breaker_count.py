"""Integration test: recent_consecutive_identical_count walks the
failed-proposal tail for a (ref_id, file_path) and counts the streak of
most-recent identical canonical signatures.

Inserts synthetic AutonomousProposal rows in `status='failed'` with
controlled `actions` JSONB and `failure_reason` text, then asserts the
count helper returns the expected streak length, signature, and
last_proposal_id.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import delete
from sqlalchemy.ext.asyncio import AsyncSession

from shared.infrastructure.database.models.autonomous_proposals import (
    AutonomousProposal,
)
from will.workers.circuit_breaker import (
    canonical_signature,
    load_circuit_breaker_config,
    recent_consecutive_identical_count,
)


pytestmark = [pytest.mark.integration]


def _failed_row(
    *,
    proposal_id: str,
    ref_id: str,
    file_path: str | None,
    failure_reason: str,
    completed_at: datetime,
    ref_kind: str = "action",
) -> AutonomousProposal:
    if ref_kind == "flow":
        action = {"flow_id": ref_id, "parameters": {"write": True}, "order": 0}
    else:
        params: dict[str, object] = {"write": True}
        if file_path is not None:
            params["file_path"] = file_path
        action = {"action_id": ref_id, "parameters": params, "order": 0}

    return AutonomousProposal(
        proposal_id=proposal_id,
        goal=f"circuit-breaker test row for {ref_id}",
        status="failed",
        actions=[action],
        scope={"files": [file_path] if file_path else []},
        constitutional_constraints={},
        approval_required=False,
        created_at=completed_at - timedelta(seconds=1),
        execution_completed_at=completed_at,
        execution_results={},
        failure_reason=failure_reason,
    )


async def _cleanup(db_session: AsyncSession, proposal_ids: list[str]) -> None:
    await db_session.rollback()
    await db_session.execute(
        delete(AutonomousProposal).where(
            AutonomousProposal.proposal_id.in_(proposal_ids)
        )
    )
    await db_session.commit()


async def test_count_returns_zero_when_no_failed_rows(
    db_session: AsyncSession,
) -> None:
    config = load_circuit_breaker_config()
    count, sig, pid, reason = await recent_consecutive_identical_count(
        db_session,
        ref_id=f"fix.unused.{uuid.uuid4().hex[:8]}",
        ref_kind="action",
        file_path="src/nonexistent.py",
        config=config,
    )
    assert count == 0
    assert sig is None
    assert pid is None
    assert reason is None


async def test_count_streak_of_five_identical_failures(
    db_session: AsyncSession,
) -> None:
    """5 failed rows for the same (ref_id, file_path) with identical
    canonical signatures → count == 5, signature stable, last_proposal_id
    is the newest row.
    """
    ref_id = f"fix.placeholders.{uuid.uuid4().hex[:8]}"
    file_path = f"src/test_circuit_{uuid.uuid4().hex[:8]}.py"
    base_time = datetime.now(UTC)
    proposal_ids: list[str] = []

    rows = []
    for i in range(5):
        pid = f"cb-test-{uuid.uuid4().hex[:12]}"
        proposal_ids.append(pid)
        rows.append(
            _failed_row(
                proposal_id=pid,
                ref_id=ref_id,
                file_path=file_path,
                failure_reason=(
                    f"IntentGuard refused: scope leak in {ref_id} "
                    f"at 2026-05-11T14:{i:02d}:00Z (took {0.17 + i:.2f}s)"
                ),
                completed_at=base_time - timedelta(minutes=i),
            )
        )

    db_session.add_all(rows)
    await db_session.commit()

    try:
        config = load_circuit_breaker_config()
        count, sig, last_pid, last_reason = await recent_consecutive_identical_count(
            db_session,
            ref_id=ref_id,
            ref_kind="action",
            file_path=file_path,
            config=config,
        )
        assert count == 5, f"expected streak=5, got {count}"
        assert sig is not None and sig != ""
        # Newest row sits at i=0 (largest completed_at because base_time-0min)
        assert last_pid == proposal_ids[0]
        assert last_reason is not None
        assert "IntentGuard refused" in last_reason
    finally:
        await _cleanup(db_session, proposal_ids)


async def test_count_streak_breaks_on_signature_mismatch(
    db_session: AsyncSession,
) -> None:
    """Newest row has a different signature from the older identical
    streak → only the newest row counts toward the streak (length 1).
    Verifies that an intervening success/different failure resets
    attribution by the consecutive-identical rule.
    """
    ref_id = f"fix.format.{uuid.uuid4().hex[:8]}"
    file_path = f"src/test_circuit_{uuid.uuid4().hex[:8]}.py"
    base_time = datetime.now(UTC)
    proposal_ids: list[str] = []
    rows = []

    # Newest row: a different error.
    pid_newest = f"cb-test-{uuid.uuid4().hex[:12]}"
    proposal_ids.append(pid_newest)
    rows.append(
        _failed_row(
            proposal_id=pid_newest,
            ref_id=ref_id,
            file_path=file_path,
            failure_reason="ModularitySplitter refused: imported symbol in plan",
            completed_at=base_time,
        )
    )

    # Older 4 rows: identical signature.
    for i in range(1, 5):
        pid = f"cb-test-{uuid.uuid4().hex[:12]}"
        proposal_ids.append(pid)
        rows.append(
            _failed_row(
                proposal_id=pid,
                ref_id=ref_id,
                file_path=file_path,
                failure_reason="IntentGuard refused: scope leak",
                completed_at=base_time - timedelta(minutes=i),
            )
        )

    db_session.add_all(rows)
    await db_session.commit()

    try:
        config = load_circuit_breaker_config()
        count, sig, last_pid, _ = await recent_consecutive_identical_count(
            db_session,
            ref_id=ref_id,
            ref_kind="action",
            file_path=file_path,
            config=config,
        )
        assert count == 1, (
            f"streak should break at the newest mismatching row, got {count}"
        )
        assert last_pid == pid_newest
        assert sig == canonical_signature(
            "ModularitySplitter refused: imported symbol in plan", config
        )
    finally:
        await _cleanup(db_session, proposal_ids)


async def test_count_isolated_per_file_path(
    db_session: AsyncSession,
) -> None:
    """5 failures on file A do not contaminate the count for file B
    even when ref_id matches. Verifies the (ref_id, file_path) key.
    """
    ref_id = f"fix.placeholders.{uuid.uuid4().hex[:8]}"
    file_a = f"src/test_circuit_a_{uuid.uuid4().hex[:8]}.py"
    file_b = f"src/test_circuit_b_{uuid.uuid4().hex[:8]}.py"
    base_time = datetime.now(UTC)
    proposal_ids: list[str] = []
    rows = []

    for i in range(5):
        pid = f"cb-test-{uuid.uuid4().hex[:12]}"
        proposal_ids.append(pid)
        rows.append(
            _failed_row(
                proposal_id=pid,
                ref_id=ref_id,
                file_path=file_a,
                failure_reason="IntentGuard refused: scope leak",
                completed_at=base_time - timedelta(minutes=i),
            )
        )

    db_session.add_all(rows)
    await db_session.commit()

    try:
        config = load_circuit_breaker_config()
        count_a, _, _, _ = await recent_consecutive_identical_count(
            db_session,
            ref_id=ref_id,
            ref_kind="action",
            file_path=file_a,
            config=config,
        )
        count_b, _, _, _ = await recent_consecutive_identical_count(
            db_session,
            ref_id=ref_id,
            ref_kind="action",
            file_path=file_b,
            config=config,
        )
        assert count_a == 5
        assert count_b == 0
    finally:
        await _cleanup(db_session, proposal_ids)
