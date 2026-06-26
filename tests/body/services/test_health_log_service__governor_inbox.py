# tests/body/services/test_health_log_service__governor_inbox.py

"""Integration test: HealthLogService governor-inbox backlog persistence (#563).

The F-19 re-anchor (governor call 2026-06-13) makes the convergence goal a
two-component backlog vector. This exercises the second component end-to-end on
the live test DB:

  - collect_system_state() returns `governor_inbox` = COUNT(DISTINCT subject) of
    `indeterminate` + `resolution_mechanism='human'` findings — distinct-subject
    dedup, with the reaudit queue excluded so it does not double-count the
    machine backlog (open_findings).
  - write_health_log() persists `governor_inbox` into system_health_log.payload
    beside flow_24h, so the inbox half of the 30-day trajectory is observable
    ("persistence mirrors metric definition").

Real WHERE clause + real round-trip on the test DB, not mocked.
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.health_log_service import HealthLogService
from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session


pytestmark = [pytest.mark.integration]


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """collect_system_state / write_health_log open their own sessions via
    ServiceRegistry.session(); bind it to the test DB session factory."""
    service_registry.prime(get_session)


async def _ensure_worker_registry_row(
    session: AsyncSession, worker_uuid: uuid.UUID
) -> None:
    """Seed a worker_registry row so blackboard_entries.worker_uuid FK is
    satisfied. On a freshly-seeded DB worker_registry is empty, so a finding
    inserted with an unregistered worker_uuid violates the FK (and aborts the
    transaction). Mirrors the sibling blackboard tests."""
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
            "worker_name": f"test_worker_{str(worker_uuid)[:8]}",
        },
    )


async def _insert_finding(
    session: AsyncSession,
    worker_uuid: uuid.UUID,
    subject: str,
    status: str,
    mechanism: str,
) -> None:
    # worker_uuid + phase are NOT NULL; worker_uuid carries an FK to
    # worker_registry; resolution_mechanism CHECK requires a finding to carry
    # one of (reaudit, self_resolve, human).
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (worker_uuid, entry_type, phase, subject, status,
                 resolution_mechanism, payload)
            VALUES
                (:worker_uuid, 'finding', 'audit', :subject, :status,
                 :mechanism, '{}'::jsonb)
            """
        ),
        {
            "worker_uuid": worker_uuid,
            "subject": subject,
            "status": status,
            "mechanism": mechanism,
        },
    )


async def _cleanup_subject(session: AsyncSession, subject: str) -> None:
    await session.execute(
        text("DELETE FROM core.blackboard_entries WHERE subject = :subject"),
        {"subject": subject},
    )
    await session.commit()


async def test_governor_inbox_counts_distinct_human_delegated_subjects(
    db_session: AsyncSession,
) -> None:
    """governor_inbox adds exactly one distinct subject for a human-delegated
    finding (two rows, one subject) and ignores a reaudit-mechanism control."""
    svc = HealthLogService()
    worker_uuid = uuid.uuid4()
    human_subject = "test.governor_inbox::human-delegated-001"
    reaudit_subject = "test.governor_inbox::reaudit-control-001"

    baseline = (await svc.collect_system_state())["governor_inbox"]
    assert isinstance(baseline, int)

    try:
        await _ensure_worker_registry_row(db_session, worker_uuid)
        # Two rows, same subject → must count as ONE distinct subject.
        await _insert_finding(
            db_session, worker_uuid, human_subject, "indeterminate", "human"
        )
        await _insert_finding(
            db_session, worker_uuid, human_subject, "indeterminate", "human"
        )
        # Control: reaudit mechanism must NOT count toward governor_inbox
        # (it belongs to the machine backlog, not the human inbox).
        await _insert_finding(
            db_session, worker_uuid, reaudit_subject, "indeterminate", "reaudit"
        )
        await db_session.commit()

        after = (await svc.collect_system_state())["governor_inbox"]
        assert after == baseline + 1, (
            "governor_inbox must add exactly one distinct human-delegated subject "
            "and exclude the reaudit control"
        )
    finally:
        await _cleanup_subject(db_session, human_subject)
        await _cleanup_subject(db_session, reaudit_subject)
        await db_session.execute(
            text("DELETE FROM core.worker_registry WHERE worker_uuid = :worker_uuid"),
            {"worker_uuid": worker_uuid},
        )
        await db_session.commit()


async def test_write_health_log_persists_governor_inbox_in_payload(
    db_session: AsyncSession,
) -> None:
    """write_health_log writes governor_inbox into system_health_log.payload,
    keeping flow_24h alongside it."""
    svc = HealthLogService()
    sentinel = 424242
    state = {
        "open_findings": 0,
        "governor_inbox": sentinel,
        "stale_entries": 0,
        "silent_workers": 0,
        "orphaned_symbols": 0,
        "flow_24h": {"created": 1, "resolved": 1, "stuck": 0, "total_open": 0},
    }

    try:
        await svc.write_health_log(state)

        row = (
            await db_session.execute(
                text(
                    """
                    SELECT payload FROM core.system_health_log
                    WHERE (payload->>'governor_inbox')::int = :sentinel
                    ORDER BY observed_at DESC LIMIT 1
                    """
                ),
                {"sentinel": sentinel},
            )
        ).fetchone()
        assert row is not None, "health-log row with sentinel governor_inbox missing"
        assert row.payload.get("governor_inbox") == sentinel
        assert "flow_24h" in row.payload, "flow_24h must persist alongside the inbox"
    finally:
        await db_session.execute(
            text(
                """
                DELETE FROM core.system_health_log
                WHERE (payload->>'governor_inbox')::int = :sentinel
                """
            ),
            {"sentinel": sentinel},
        )
        await db_session.commit()
