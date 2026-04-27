"""Integration test: ViolationRemediatorWorker._resolve_entries records the
subsuming proposal_id in each subsumed finding's payload (Edge 1 / ADR-015 D4).

The dedup-subsume path used to close findings as 'resolved' with no audit
linkage back to the subsuming proposal — Q1.F (URS) and ADR-015 D4 require
the proposal_id to be carried in payload so consequence-log queries can
attribute the resolved finding to the proposal that subsumed it.

Setup ensures the core.blackboard_entries table exists in the test DB
(it is not always present in core_test); the model has no FK to
worker_registry, so a synthetic worker_uuid is sufficient.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.service_registry import service_registry
from shared.infrastructure.database.models.workers import BlackboardEntry
from shared.infrastructure.database.session_manager import get_session
from will.workers.violation_remediator import ViolationRemediatorWorker


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Mirror the production entry-point bootstrap so service_registry.session()
    inside the worker can acquire a live session against core_test."""
    service_registry.prime(get_session)


async def _ensure_blackboard_table(session: AsyncSession) -> None:
    """Create core.blackboard_entries if it is missing in the test DB.

    The production schema includes an FK on worker_uuid that the SQLAlchemy
    model does not declare; create_all therefore creates the table without
    that constraint, which is what this test wants — the worker_uuid here
    is synthetic and need not refer to worker_registry.
    """
    await session.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
    conn = await session.connection()
    await conn.run_sync(
        BlackboardEntry.__table__.create,  # type: ignore[attr-defined]
        checkfirst=True,
    )
    await session.commit()


async def test_resolve_entries_records_subsuming_proposal_id(
    db_session: AsyncSession,
) -> None:
    """Two synthetic claimed findings → _resolve_entries(ids, proposal_id)
    transitions both to 'resolved' with the proposal_id in payload and
    resolved_at populated.
    """
    await _ensure_blackboard_table(db_session)

    worker = ViolationRemediatorWorker(declaration_name="violation_remediator")
    worker_uuid = worker._worker_uuid
    phase = worker._phase

    entry_id_a = uuid.uuid4()
    entry_id_b = uuid.uuid4()
    subsuming_proposal_id = str(uuid.uuid4())

    payload_a = {
        "file_path": "src/test_fixture_subsume_a.py",
        "check_id": "workflow.ruff_format_check",
        "rule": "workflow.ruff_format_check",
    }
    payload_b = {
        "file_path": "src/test_fixture_subsume_b.py",
        "check_id": "workflow.ruff_format_check",
        "rule": "workflow.ruff_format_check",
    }

    insert_sql = text(
        """
        INSERT INTO core.blackboard_entries
            (id, worker_uuid, entry_type, phase, status, subject, payload,
             claimed_by, claimed_at)
        VALUES
            (:id, :worker_uuid, 'finding', :phase, 'claimed',
             'audit.violation::workflow.ruff_format_check',
             cast(:payload as jsonb), :worker_uuid, now())
        """
    )

    await db_session.execute(
        insert_sql,
        {
            "id": entry_id_a,
            "worker_uuid": worker_uuid,
            "phase": phase,
            "payload": json.dumps(payload_a),
        },
    )
    await db_session.execute(
        insert_sql,
        {
            "id": entry_id_b,
            "worker_uuid": worker_uuid,
            "phase": phase,
            "payload": json.dumps(payload_b),
        },
    )
    await db_session.commit()

    try:
        resolved_count = await worker._resolve_entries(
            [str(entry_id_a), str(entry_id_b)], subsuming_proposal_id
        )
        assert resolved_count == 2, (
            f"_resolve_entries reported {resolved_count} updates, expected 2"
        )

        db_session.expire_all()
        result = await db_session.execute(
            text(
                """
                SELECT id, status, resolved_at, payload->>'proposal_id'
                FROM core.blackboard_entries
                WHERE id IN (:id_a, :id_b)
                ORDER BY id
                """
            ),
            {"id_a": entry_id_a, "id_b": entry_id_b},
        )
        rows = result.fetchall()
        assert len(rows) == 2, f"expected 2 rows back, got {len(rows)}"

        for row in rows:
            row_id, status, resolved_at, payload_proposal_id = row
            assert status == "resolved", (
                f"row {row_id}: status={status!r}, expected 'resolved'"
            )
            assert resolved_at is not None, (
                f"row {row_id}: resolved_at is NULL — terminal-state hygiene "
                "rule violated"
            )
            assert payload_proposal_id == subsuming_proposal_id, (
                f"row {row_id}: payload->>'proposal_id' = {payload_proposal_id!r}, "
                f"expected {subsuming_proposal_id!r}"
            )
    finally:
        await db_session.execute(
            text(
                "DELETE FROM core.blackboard_entries WHERE id IN (:id_a, :id_b)"
            ),
            {"id_a": entry_id_a, "id_b": entry_id_b},
        )
        await db_session.commit()
