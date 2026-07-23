"""Integration tests for ADR-104 D9 counter inheritance in TestRemediatorWorker.

Verifies that _query_source_file_attempt_count and _inherit_attempt_count
prevent the remediation cap from being bypassed when sensors re-detect an
unresolved source_file after its prior findings were abandoned at cap_n.

Setup mirrors test_test_remediator_defer_to_proposal.py: real core_test DB,
synthetic worker_uuid, cleanup in finally blocks.
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
from will.workers.test_remediator._operations import (
    _inherit_attempt_count,
    _query_source_file_attempt_count,
)


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
            "worker_name": f"test_count_inherit_{str(worker_uuid)[:8]}",
        },
    )


async def _insert_entry(
    session: AsyncSession,
    *,
    entry_id: uuid.UUID,
    worker_uuid: uuid.UUID,
    phase: str,
    status: str,
    source_file: str,
    attempt_count: int | None = None,
) -> None:
    payload: dict[str, object] = {"source_file": source_file}
    if attempt_count is not None:
        payload["remediation_attempt_count"] = attempt_count

    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject, payload,
                 resolution_mechanism, claimed_by, claimed_at)
            VALUES
                (:id, :worker_uuid, 'finding', :phase, :status,
                 :subject, cast(:payload as jsonb), 'reaudit',
                 :worker_uuid, now())
            """
        ),
        {
            "id": entry_id,
            "worker_uuid": worker_uuid,
            "phase": phase,
            "status": status,
            "subject": f"python::test.runner.missing::{source_file}",
            "payload": json.dumps(payload),
        },
    )


async def test_query_max_count_returns_highest_abandoned_count(
    db_session: AsyncSession,
) -> None:
    """_query_source_file_attempt_count returns the max count from abandoned
    findings for that source_file, ignoring other statuses."""
    await _ensure_blackboard_table(db_session)

    worker = TestRemediatorWorker(declaration_name="test_remediator")
    worker_uuid = worker._worker_uuid
    phase = worker._phase
    await _ensure_worker_registry_row(db_session, worker_uuid)

    source_file = "src/body/services/count_inherit_fixture_a.py"
    id_abandoned_2 = uuid.uuid4()
    id_abandoned_3 = uuid.uuid4()
    id_open_0 = uuid.uuid4()

    await _insert_entry(
        db_session,
        entry_id=id_abandoned_2,
        worker_uuid=worker_uuid,
        phase=phase,
        status="abandoned",
        source_file=source_file,
        attempt_count=2,
    )
    await _insert_entry(
        db_session,
        entry_id=id_abandoned_3,
        worker_uuid=worker_uuid,
        phase=phase,
        status="abandoned",
        source_file=source_file,
        attempt_count=3,
    )
    # A fresh open finding (count absent) for same source_file — should not
    # influence the max.
    await _insert_entry(
        db_session,
        entry_id=id_open_0,
        worker_uuid=worker_uuid,
        phase=phase,
        status="open",
        source_file=source_file,
    )
    await db_session.commit()

    try:
        result = await _query_source_file_attempt_count(source_file)
        assert result == 3, f"expected max abandoned count 3, got {result}"
    finally:
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id IN (:a, :b, :c)"),
            {"a": id_abandoned_2, "b": id_abandoned_3, "c": id_open_0},
        )
        await db_session.commit()


async def test_query_max_count_returns_zero_when_no_abandoned(
    db_session: AsyncSession,
) -> None:
    """Returns 0 when the source_file has no abandoned findings."""
    await _ensure_blackboard_table(db_session)

    result = await _query_source_file_attempt_count(
        "src/body/services/no_abandoned_fixture.py"
    )
    assert result == 0


async def test_inherit_attempt_count_sets_payload_field(
    db_session: AsyncSession,
) -> None:
    """_inherit_attempt_count raises the count to max(existing, inherited)
    for claimed entries and leaves other statuses untouched."""
    await _ensure_blackboard_table(db_session)

    worker = TestRemediatorWorker(declaration_name="test_remediator")
    worker_uuid = worker._worker_uuid
    phase = worker._phase
    await _ensure_worker_registry_row(db_session, worker_uuid)

    # Distinct source_files -> distinct subjects: the active-finding dedup
    # invariant (uq_active_finding_identity) forbids two non-terminal findings
    # per (subject, resolution_mechanism). _inherit_attempt_count operates by
    # id + status regardless of subject, so distinct subjects preserve intent.
    source_file = "src/body/services/count_inherit_fixture_b.py"
    source_file_high = "src/body/services/count_inherit_fixture_b_high.py"
    id_claimed_low = uuid.uuid4()  # count=1, should be raised to 3
    id_claimed_high = uuid.uuid4()  # count=5, should stay 5 (GREATEST)
    id_abandoned = uuid.uuid4()  # should NOT be touched (status filter)

    await _insert_entry(
        db_session,
        entry_id=id_claimed_low,
        worker_uuid=worker_uuid,
        phase=phase,
        status="claimed",
        source_file=source_file,
        attempt_count=1,
    )
    await _insert_entry(
        db_session,
        entry_id=id_claimed_high,
        worker_uuid=worker_uuid,
        phase=phase,
        status="claimed",
        source_file=source_file_high,
        attempt_count=5,
    )
    await _insert_entry(
        db_session,
        entry_id=id_abandoned,
        worker_uuid=worker_uuid,
        phase=phase,
        status="abandoned",
        source_file=source_file,
        attempt_count=2,
    )
    await db_session.commit()

    try:
        await _inherit_attempt_count(
            [str(id_claimed_low), str(id_claimed_high), str(id_abandoned)],
            count=3,
        )

        db_session.expire_all()
        result = await db_session.execute(
            text(
                """
                SELECT id,
                       (payload->>'remediation_attempt_count')::int AS cnt
                FROM core.blackboard_entries
                WHERE id IN (:a, :b, :c)
                ORDER BY id
                """
            ),
            {"a": id_claimed_low, "b": id_claimed_high, "c": id_abandoned},
        )
        rows = {str(r[0]): r[1] for r in result.fetchall()}

        assert rows[str(id_claimed_low)] == 3, (
            f"claimed entry with count=1 should be raised to 3, "
            f"got {rows[str(id_claimed_low)]}"
        )
        assert rows[str(id_claimed_high)] == 5, (
            f"claimed entry with count=5 should stay 5 (GREATEST), "
            f"got {rows[str(id_claimed_high)]}"
        )
        assert rows[str(id_abandoned)] == 2, (
            f"abandoned entry must not be updated (status filter), "
            f"got {rows[str(id_abandoned)]}"
        )
    finally:
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id IN (:a, :b, :c)"),
            {"a": id_claimed_low, "b": id_claimed_high, "c": id_abandoned},
        )
        await db_session.commit()
