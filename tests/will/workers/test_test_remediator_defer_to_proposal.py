"""Integration test: TestRemediatorWorker._defer_to_proposal records the
created proposal_id in each consumed finding's payload and transitions
those findings to 'deferred_to_proposal' (CORE-Finding.md §7 row 4 / ADR-010).

The test stream used to close findings as 'resolved' with no audit linkage
back to the proposal — the §7a revival contract in
ProposalStateManager.mark_failed depends on the deferred_to_proposal
status plus the proposal_id payload pointer being present.

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
from will.workers.test_remediator import TestRemediatorWorker
from will.workers.test_remediator._operations import _defer_to_proposal


pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Mirror the production entry-point bootstrap so service_registry.session()
    inside the worker can acquire a live session against core_test."""
    service_registry.prime(get_session)


async def _ensure_blackboard_table(session: AsyncSession) -> None:
    """Create core.blackboard_entries if it is missing in the test DB.

    The live test DB enforces FK on worker_uuid → worker_registry plus a
    CHECK on resolution_mechanism (ADR-091 D2 Revision B). Both constraints
    exist regardless of what create_all reproduces; see
    _ensure_worker_registry_row and the resolution_mechanism column on the
    INSERT below.
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
    """Seed a worker_registry row to satisfy blackboard_entries FK."""
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
            "worker_name": f"test_defer_to_proposal_{str(worker_uuid)[:8]}",
        },
    )


async def test_defer_to_proposal_records_proposal_id_and_transitions_status(
    db_session: AsyncSession,
) -> None:
    """Two synthetic claimed test-stream findings → _defer_to_proposal(ids, pid)
    transitions both to 'deferred_to_proposal' with the proposal_id stamped
    into payload and resolved_at populated.
    """
    await _ensure_blackboard_table(db_session)

    worker = TestRemediatorWorker(declaration_name="test_remediator")
    worker_uuid = worker._worker_uuid
    phase = worker._phase

    entry_id_a = uuid.uuid4()
    entry_id_b = uuid.uuid4()
    proposal_id = str(uuid.uuid4())

    payload_a = {
        "source_file": "src/test_fixture_defer_a.py",
        "rule": "test.missing",
    }
    payload_b = {
        "source_file": "src/test_fixture_defer_a.py",
        "rule": "test.failure",
    }

    await _ensure_worker_registry_row(db_session, worker_uuid)

    insert_sql = text(
        """
        INSERT INTO core.blackboard_entries
            (id, worker_uuid, entry_type, phase, status, subject, payload,
             resolution_mechanism, claimed_by, claimed_at)
        VALUES
            (:id, :worker_uuid, 'finding', :phase, 'claimed',
             :subject, cast(:payload as jsonb), 'reaudit',
             :worker_uuid, now())
        """
    )

    await db_session.execute(
        insert_sql,
        {
            "id": entry_id_a,
            "worker_uuid": worker_uuid,
            "phase": phase,
            "subject": "test.missing::src/test_fixture_defer_a.py",
            "payload": json.dumps(payload_a),
        },
    )
    await db_session.execute(
        insert_sql,
        {
            "id": entry_id_b,
            "worker_uuid": worker_uuid,
            "phase": phase,
            "subject": "test.failure::tests/test_fixture_defer_a.py::test_x",
            "payload": json.dumps(payload_b),
        },
    )
    await db_session.commit()

    try:
        deferred_count = await _defer_to_proposal(
            [str(entry_id_a), str(entry_id_b)], proposal_id
        )
        assert deferred_count == 2, (
            f"_defer_to_proposal reported {deferred_count} updates, expected 2"
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
            assert status == "deferred_to_proposal", (
                f"row {row_id}: status={status!r}, expected 'deferred_to_proposal'"
            )
            assert resolved_at is not None, (
                f"row {row_id}: resolved_at is NULL — terminal-state hygiene "
                "rule violated"
            )
            assert payload_proposal_id == proposal_id, (
                f"row {row_id}: payload->>'proposal_id' = {payload_proposal_id!r}, "
                f"expected {proposal_id!r}"
            )
    finally:
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id IN (:id_a, :id_b)"),
            {"id_a": entry_id_a, "id_b": entry_id_b},
        )
        await db_session.commit()
