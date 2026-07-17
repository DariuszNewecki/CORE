"""Integration test: BlackboardService.adjudicate_abandoned_findings (ADR-127 D7).

Seeds Type-B 'abandoned' findings (ViolationExecutorWorker's remediation-
attempt-cap abandons, ADR-104 D9) under the same rule namespace, then calls
the adjudication method with a current-violation set. Asserts:

- A finding whose subject IS in the current set stays 'abandoned' (the
  daemon genuinely could not self-heal this; the signal must survive).
- A finding whose subject is NOT in the current set transitions to
  'resolved' with payload.resolution carrying system.audit attribution.
- Only 'resolved_subjects' is returned (no 'released_subjects').
- Namespace scoping: an abandoned finding under a different namespace is
  not touched by the drain pass.
- Type-A abandoned entries (e.g. loop_hold.sample::<stem>) are never
  selected — not because of an added filter, but because their subject
  shape can never match an <artifact_type>::<rule_namespace> prefix.

Mirrors test_adjudicate_indeterminate.py; covers ADR-127 addendum D7.
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
            "worker_name": f"test_worker_{str(worker_uuid)[:8]}",
        },
    )


async def _seed_abandoned_finding(
    session: AsyncSession,
    *,
    finding_id: uuid.UUID,
    worker_uuid: uuid.UUID,
    subject: str,
    rule: str,
    file_path: str,
) -> None:
    """Insert a Type-B finding in 'abandoned' status with resolution_mechanism='reaudit'.

    'reaudit' matches production reality: audit-violation findings are posted
    via post_artifact_finding (resolution_mechanism='reaudit', see
    blackboard_publisher.py), and abandon_entries_and_increment_attempt_count
    (ADR-104 D9) transitions status without touching resolution_mechanism.
    """
    await _ensure_worker_registry_row(session, worker_uuid)
    payload = {
        "rule": rule,
        "file_path": file_path,
        "message": "synthetic - abandoned adjudication test",
        "remediation_attempt_count": 3,
    }
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject,
                 payload, resolution_mechanism,
                 claimed_by, claimed_at, resolved_at)
            VALUES
                (:id, :worker_uuid, 'finding', 'parse', 'abandoned',
                 :subject, cast(:payload as jsonb), 'reaudit',
                 NULL, NULL, now())
            """
        ),
        {
            "id": finding_id,
            "worker_uuid": worker_uuid,
            "subject": subject,
            "payload": json.dumps(payload),
        },
    )


async def test_abandoned_clean_pass_resolves_cleared_and_leaves_held(
    db_session: AsyncSession,
) -> None:
    """ADR-127 D7: a Type-B abandoned finding whose violation is gone →
    resolved; one whose violation still holds → stays abandoned.
    """
    await _ensure_blackboard_table(db_session)

    namespace = f"testns_{uuid.uuid4().hex[:8]}"
    rule_held = f"{namespace}.still_violating"
    rule_cleared = f"{namespace}.no_longer_violating"
    file_held = "src/test/still_violating.py"
    file_cleared = "src/test/no_longer_violating.py"
    subject_held = f"python::{rule_held}::{file_held}"
    subject_cleared = f"python::{rule_cleared}::{file_cleared}"

    finding_held = uuid.uuid4()
    finding_cleared = uuid.uuid4()
    worker_uuid = uuid.uuid4()

    await _seed_abandoned_finding(
        db_session,
        finding_id=finding_held,
        worker_uuid=worker_uuid,
        subject=subject_held,
        rule=rule_held,
        file_path=file_held,
    )
    await _seed_abandoned_finding(
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
        result = await service.adjudicate_abandoned_findings(
            subject_prefix=f"python::{namespace}",
            current_violation_subjects={subject_held},
            resolved_by="audit_violation_sensor",
        )

        assert result["resolved_subjects"] == [subject_cleared], (
            f"expected only {subject_cleared} resolved, got {result['resolved_subjects']}"
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

        assert held_row[1] == "abandoned", (
            f"held finding was mutated: status={held_row[1]!r}, expected 'abandoned'"
        )
        assert held_row[3] is None, "held finding must not have payload.resolution"

        assert cleared_row[1] == "resolved", (
            f"cleared finding status={cleared_row[1]!r}, expected 'resolved'"
        )
        assert cleared_row[2] is not None, "resolved finding must have resolved_at"
        resolution = cleared_row[3]
        assert resolution is not None, "resolved finding missing payload.resolution"
        assert resolution["resolved_by"] == "audit_violation_sensor"
        assert resolution["resolution_authority"] == "system.audit"
        assert "ADR-127 D7" in resolution["reason"]
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


async def test_abandoned_clean_pass_returns_empty_when_no_queue(
    db_session: AsyncSession,
) -> None:
    """No abandoned findings under namespace → empty result, no mutations."""
    await _ensure_blackboard_table(db_session)

    namespace = f"empty_ns_{uuid.uuid4().hex[:8]}"
    service = BlackboardService()
    result = await service.adjudicate_abandoned_findings(
        subject_prefix=f"python::{namespace}",
        current_violation_subjects=set(),
        resolved_by="audit_violation_sensor",
    )

    assert result["resolved_subjects"] == []


async def test_abandoned_clean_pass_does_not_touch_other_namespace(
    db_session: AsyncSession,
) -> None:
    """ADR-127 D7: namespace scoping — an abandoned finding under namespace
    'other' is not resolved by a drain pass scoped to namespace 'target'.
    """
    await _ensure_blackboard_table(db_session)

    ns_target = f"target_{uuid.uuid4().hex[:8]}"
    ns_other = f"other_{uuid.uuid4().hex[:8]}"

    other_finding = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    subject_other = f"python::{ns_other}.some_rule::src/test/x.py"

    await _seed_abandoned_finding(
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
        result = await service.adjudicate_abandoned_findings(
            subject_prefix=f"python::{ns_target}",
            current_violation_subjects=set(),
            resolved_by="audit_violation_sensor",
        )

        assert result["resolved_subjects"] == []

        db_session.expire_all()
        row = await db_session.execute(
            text("SELECT status FROM core.blackboard_entries WHERE id = :id"),
            {"id": other_finding},
        )
        status = row.scalar()
        assert status == "abandoned", (
            f"other-namespace finding was touched: status={status!r}"
        )
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": other_finding},
        )
        await db_session.commit()


async def test_all_violations_held_resolves_nothing(
    db_session: AsyncSession,
) -> None:
    """ADR-127 D7: if every abandoned finding's violation still holds,
    nothing is resolved — the drain pass is conservative.
    """
    await _ensure_blackboard_table(db_session)

    namespace = f"allheld_{uuid.uuid4().hex[:8]}"
    rule = f"{namespace}.always_fires"
    file_path = "src/test/always_fires.py"
    subject = f"python::{rule}::{file_path}"
    finding_id = uuid.uuid4()
    worker_uuid = uuid.uuid4()

    await _seed_abandoned_finding(
        db_session,
        finding_id=finding_id,
        worker_uuid=worker_uuid,
        subject=subject,
        rule=rule,
        file_path=file_path,
    )
    await db_session.commit()

    try:
        service = BlackboardService()
        result = await service.adjudicate_abandoned_findings(
            subject_prefix=f"python::{namespace}",
            current_violation_subjects={subject},
            resolved_by="audit_violation_sensor",
        )

        assert result["resolved_subjects"] == []

        db_session.expire_all()
        row = await db_session.execute(
            text("SELECT status FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        assert row.scalar() == "abandoned"
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": finding_id},
        )
        await db_session.commit()


async def test_type_a_abandoned_telemetry_never_selected(
    db_session: AsyncSession,
) -> None:
    """ADR-127 D7: a Type-A telemetry abandon (loop_hold.sample::<stem> shape)
    is structurally invisible to this drain — its subject can never match an
    <artifact_type>::<rule_namespace> prefix, regardless of current_violation_subjects.
    """
    await _ensure_blackboard_table(db_session)

    namespace = f"typea_ns_{uuid.uuid4().hex[:8]}"
    telemetry_finding = uuid.uuid4()
    worker_uuid = uuid.uuid4()
    # Type-A shape: no "::" prefix matching <artifact_type>::<rule_namespace>.
    subject_telemetry = f"loop_hold.sample::some_worker_stem_{uuid.uuid4().hex[:8]}"

    await _seed_abandoned_finding(
        db_session,
        finding_id=telemetry_finding,
        worker_uuid=worker_uuid,
        subject=subject_telemetry,
        rule="n/a",
        file_path="n/a",
    )
    await db_session.commit()

    try:
        service = BlackboardService()
        result = await service.adjudicate_abandoned_findings(
            subject_prefix=f"python::{namespace}",
            current_violation_subjects=set(),
            resolved_by="audit_violation_sensor",
        )

        assert result["resolved_subjects"] == []

        db_session.expire_all()
        row = await db_session.execute(
            text("SELECT status FROM core.blackboard_entries WHERE id = :id"),
            {"id": telemetry_finding},
        )
        assert row.scalar() == "abandoned", (
            "Type-A telemetry abandon must never be touched by the drain"
        )
    finally:
        await db_session.rollback()
        await db_session.execute(
            text("DELETE FROM core.blackboard_entries WHERE id = :id"),
            {"id": telemetry_finding},
        )
        await db_session.commit()
