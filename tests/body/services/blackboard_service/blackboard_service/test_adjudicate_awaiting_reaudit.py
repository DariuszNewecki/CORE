"""Integration test: BlackboardService.adjudicate_awaiting_reaudit_findings (ADR-045).

Seeds two findings in 'awaiting_reaudit' status under the same rule
namespace, then calls the adjudication method with a current-violation
set that contains exactly one of the two subjects. Asserts:

- The subject in the current set transitions to 'open' with no
  payload.resolution stamped.
- The subject absent from the current set transitions to 'resolved' with
  payload.resolution carrying system.audit attribution.
- Both transitions land in one transaction (verified indirectly: status
  count after the call).

This covers ADR-045 acceptance conditions 1 and 2 (release vs. resolve).
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.blackboard_service import BlackboardService
from body.services.service_registry import service_registry
from shared.infrastructure.database.models.workers import BlackboardEntry
from shared.infrastructure.database.session_manager import get_session


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Bind the registry to the test DB session factory."""
    service_registry.prime(get_session)


async def _ensure_blackboard_table(session: AsyncSession) -> None:
    """Create core.blackboard_entries if it is missing in the test DB."""
    await session.execute(text("CREATE SCHEMA IF NOT EXISTS core"))
    conn = await session.connection()
    await conn.run_sync(
        BlackboardEntry.__table__.create,  # type: ignore[attr-defined]
        checkfirst=True,
    )
    await session.commit()


async def _seed_quarantined_finding(
    session: AsyncSession,
    *,
    finding_id: uuid.UUID,
    worker_uuid: uuid.UUID,
    subject: str,
    rule: str,
    file_path: str,
) -> None:
    """Insert a finding directly in 'awaiting_reaudit' state."""
    payload = {
        "rule": rule,
        "file_path": file_path,
        "message": "synthetic — adjudication test",
    }
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, claimed_by, claimed_at, resolved_at)
            VALUES
                (:id, :worker_uuid, 'finding', 'parse', 'awaiting_reaudit',
                 :subject, cast(:payload as jsonb), NULL, NULL, NULL)
            """
        ),
        {
            "id": finding_id,
            "worker_uuid": worker_uuid,
            "subject": subject,
            "payload": json.dumps(payload),
        },
    )


async def test_adjudicate_releases_present_and_resolves_absent(
    db_session: AsyncSession,
) -> None:
    """Two quarantined findings under namespace 'testns'; current
    violations contain only the first subject. The first must release
    to 'open'; the second must resolve with system.audit attribution.
    """
    await _ensure_blackboard_table(db_session)

    namespace = f"testns_{uuid.uuid4().hex[:8]}"
    rule_held = f"{namespace}.still_violating"
    rule_cleared = f"{namespace}.no_longer_violating"
    file_held = "src/test/still_violating.py"
    file_cleared = "src/test/no_longer_violating.py"
    subject_held = f"audit.violation::{rule_held}::{file_held}"
    subject_cleared = f"audit.violation::{rule_cleared}::{file_cleared}"

    finding_held = uuid.uuid4()
    finding_cleared = uuid.uuid4()
    worker_uuid = uuid.uuid4()

    await _seed_quarantined_finding(
        db_session,
        finding_id=finding_held,
        worker_uuid=worker_uuid,
        subject=subject_held,
        rule=rule_held,
        file_path=file_held,
    )
    await _seed_quarantined_finding(
        db_session,
        finding_id=finding_cleared,
        worker_uuid=worker_uuid,
        subject=subject_cleared,
        rule=rule_cleared,
        file_path=file_cleared,
    )
    await db_session.commit()

    try:
        service = BlackboardService()
        result = await service.adjudicate_awaiting_reaudit_findings(
            rule_namespace=namespace,
            current_violation_subjects={subject_held},
        )

        assert result["released_subjects"] == [subject_held], (
            f"expected only {subject_held} released, got {result['released_subjects']}"
        )
        assert result["resolved_subjects"] == [subject_cleared], (
            f"expected only {subject_cleared} resolved, got "
            f"{result['resolved_subjects']}"
        )

        db_session.expire_all()
        rows = await db_session.execute(
            text(
                "SELECT id, status, resolved_at, "
                "payload->'resolution' AS resolution "
                "FROM core.blackboard_entries "
                "WHERE id IN (:id_held, :id_cleared)"
            ),
            {"id_held": finding_held, "id_cleared": finding_cleared},
        )
        by_id = {str(r[0]): r for r in rows.fetchall()}

        held_row = by_id[str(finding_held)]
        cleared_row = by_id[str(finding_cleared)]

        assert held_row[1] == "open", (
            f"held finding status={held_row[1]!r}, expected 'open'"
        )
        assert held_row[2] is None, (
            "released-to-open finding must have resolved_at=NULL"
        )
        assert held_row[3] is None, (
            "released-to-open finding must not have payload.resolution stamped"
        )

        assert cleared_row[1] == "resolved", (
            f"cleared finding status={cleared_row[1]!r}, expected 'resolved'"
        )
        assert cleared_row[2] is not None, (
            "resolved finding must have resolved_at stamped"
        )
        resolution = cleared_row[3]
        assert resolution is not None, "resolved finding missing payload.resolution"
        assert resolution["resolved_by"] == "audit_violation_sensor"
        assert resolution["resolution_authority"] == "system.audit"
        assert "no longer present" in resolution["reason"]
    finally:
        await db_session.rollback()
        await db_session.execute(
            text(
                "DELETE FROM core.blackboard_entries "
                "WHERE id IN (:id_held, :id_cleared)"
            ),
            {"id_held": finding_held, "id_cleared": finding_cleared},
        )
        await db_session.commit()


async def test_adjudicate_returns_empty_when_queue_is_empty(
    db_session: AsyncSession,
) -> None:
    """If no findings are quarantined under the namespace, both result
    lists are empty and no database mutation occurs.
    """
    await _ensure_blackboard_table(db_session)

    namespace = f"empty_ns_{uuid.uuid4().hex[:8]}"

    service = BlackboardService()
    result = await service.adjudicate_awaiting_reaudit_findings(
        rule_namespace=namespace,
        current_violation_subjects=set(),
    )

    assert result["released_subjects"] == []
    assert result["resolved_subjects"] == []


async def test_adjudicate_only_touches_matching_namespace(
    db_session: AsyncSession,
) -> None:
    """A quarantined finding under namespace 'foo' must not be adjudicated
    by a release pass scoped to namespace 'bar' — sensors are
    namespace-scoped and must not step on each other's queues.
    """
    await _ensure_blackboard_table(db_session)

    ns_target = f"target_{uuid.uuid4().hex[:8]}"
    ns_other = f"other_{uuid.uuid4().hex[:8]}"

    other_finding = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    subject_other = f"audit.violation::{ns_other}.some_rule::src/test/x.py"

    await _seed_quarantined_finding(
        db_session,
        finding_id=other_finding,
        worker_uuid=worker_uuid,
        subject=subject_other,
        rule=f"{ns_other}.some_rule",
        file_path="src/test/x.py",
    )
    await db_session.commit()

    try:
        service = BlackboardService()
        result = await service.adjudicate_awaiting_reaudit_findings(
            rule_namespace=ns_target,
            current_violation_subjects=set(),
        )

        assert result["released_subjects"] == []
        assert result["resolved_subjects"] == []

        db_session.expire_all()
        row = await db_session.execute(
            text("SELECT status FROM core.blackboard_entries WHERE id = :id"),
            {"id": other_finding},
        )
        status = row.scalar()
        assert status == "awaiting_reaudit", (
            f"other-namespace finding was touched: status={status!r}"
        )
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": other_finding},
        )
        await db_session.commit()
