# tests/body/services/blackboard_service/blackboard_service/test_noop_cap_delegation.py
"""Integration tests for ADR-104 D10 (#901) — the no-op remediation loop
terminates in the governor inbox.

``BlackboardService.revive_or_delegate_findings_for_noop_proposal`` is the
no-op counterpart of the D9 predicate with a different terminal: below the
cap a finding revived from a NOTHING_TO_COMMIT completion is routed to
awaiting_reaudit with the counter incremented (identical to D9); at the cap
it is delegated — ``status='indeterminate'``, ``resolution_mechanism='human'``
(ADR-091 D2 Amendment; ``indeterminate_requires_human_mechanism``) — not
abandoned. Acceptance criteria 8-10 against the live test DB:

  * criterion 8: at cap → indeterminate/human, counter incremented, claim
    markers cleared, ``payload.delegation.reason = 'noop_cap_delegated'``,
    surfaced in the delegated set; below cap → awaiting_reaudit as D9;
  * criterion 9: the D9 failure path is untouched — pinned by
    test_remediation_attempt_cap.py, not duplicated here;
  * criterion 10 (the load-bearing invariant): the delegated finding
    survives N sensor cycles while the violation persists — it stays in the
    sensor's active-subject dedup set (no re-post) and ADR-127's clean-pass
    drain leaves it alone — and is closed by that drain, and only that
    drain, once the violation clears.

Synthetic UUIDs + self-cleanup, same pattern as test_remediation_attempt_cap.py.
"""

from __future__ import annotations

import json
import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.blackboard_service import BlackboardService
from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session


pytestmark = [pytest.mark.integration]

_SYNTH_NAME = "test.adr104.d10.synthetic"
_CAP = 3
_RULE = "architecture.channels.logic_no_terminal_rendering"


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    service_registry.prime(get_session)


async def _register_worker(db_session: AsyncSession, worker_uuid: uuid.UUID) -> None:
    await db_session.execute(
        text(
            """
            insert into core.worker_registry
                (worker_uuid, worker_name, worker_class, phase, last_heartbeat)
            values (:u, :n, 'test', 'audit', now())
            on conflict (worker_uuid) do nothing
            """
        ),
        {"u": worker_uuid, "n": _SYNTH_NAME},
    )
    await db_session.commit()


async def _insert_deferred_finding(
    db_session: AsyncSession,
    *,
    entry_id: str,
    worker_uuid: uuid.UUID,
    proposal_id: str,
    subject: str,
    attempt_count: int | None = None,
) -> None:
    await _register_worker(db_session, worker_uuid)
    payload: dict[str, object] = {
        "file_path": subject.rsplit("::", 1)[-1],
        "rule": _RULE,
        "proposal_id": proposal_id,
    }
    if attempt_count is not None:
        payload["remediation_attempt_count"] = attempt_count
    await db_session.execute(
        text(
            """
            insert into core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject, payload,
                 resolution_mechanism, claimed_by, claimed_at, resolved_at)
            values
                (cast(:id as uuid), :worker_uuid, 'finding', 'audit',
                 'deferred_to_proposal', :subject,
                 cast(:payload as jsonb), 'reaudit',
                 :worker_uuid, now(), now())
            """
        ),
        {
            "id": entry_id,
            "worker_uuid": worker_uuid,
            "subject": subject,
            "payload": json.dumps(payload),
        },
    )
    await db_session.commit()


async def _fetch(db_session: AsyncSession, entry_id: str):
    db_session.expire_all()
    result = await db_session.execute(
        text(
            """
            select status,
                   resolution_mechanism,
                   claimed_by,
                   resolved_at,
                   (payload->>'remediation_attempt_count')::int as attempt_count,
                   payload->'delegation' as delegation
              from core.blackboard_entries
             where id = cast(:id as uuid)
            """
        ),
        {"id": entry_id},
    )
    return result.one()


async def _cleanup(
    db_session: AsyncSession, entry_id: str, worker_uuid: uuid.UUID
) -> None:
    await db_session.execute(
        text("delete from core.blackboard_entries where id = cast(:id as uuid)"),
        {"id": entry_id},
    )
    await db_session.execute(
        text(
            "delete from core.worker_registry where worker_uuid = :u and worker_name = :n"
        ),
        {"u": worker_uuid, "n": _SYNTH_NAME},
    )
    await db_session.commit()


def _subject() -> str:
    return f"python::{_RULE}::src/t901_{uuid.uuid4().hex[:8]}.py"


def _isolated_subject() -> tuple[str, str]:
    """A subject under a rule namespace unique to this test run, so the
    prefix-scoped sensor queries below cannot touch any other row that a
    parallel test left in the shared test DB. Returns (subject, prefix)."""
    namespace = f"t901ns{uuid.uuid4().hex[:8]}"
    return (
        f"python::{namespace}.no_terminal_rendering::src/t901_{uuid.uuid4().hex[:6]}.py",
        f"python::{namespace}",
    )


# ID: 96a352c9-41f4-4fb3-959a-649933f4c05c
async def test_below_cap_revives_exactly_as_d9(db_session: AsyncSession) -> None:
    emitter = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    proposal_id = f"test-d10-below-{uuid.uuid4().hex[:8]}"
    await _insert_deferred_finding(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        proposal_id=proposal_id,
        subject=_subject(),
        attempt_count=_CAP - 2,
    )
    try:
        revival = (
            await BlackboardService().revive_or_delegate_findings_for_noop_proposal(
                proposal_id=proposal_id,
                reason="nothing to commit",
                remediation_cap_n=_CAP,
            )
        )
        assert revival is not None
        assert revival["revived_count"] == 1 and revival["delegated_count"] == 0
        row = await _fetch(db_session, entry_id)
        assert row.status == "awaiting_reaudit"
        assert row.resolution_mechanism == "reaudit"
        assert row.claimed_by is None and row.resolved_at is None
        assert row.attempt_count == _CAP - 1
        assert row.delegation is None
    finally:
        await _cleanup(db_session, entry_id, emitter)


# ID: 000f0087-1b54-4e76-a34b-6755b27cdc48
async def test_at_cap_delegates_to_the_governor(db_session: AsyncSession) -> None:
    """Criterion 8: with cap=3 and a prior count of 2, this no-op takes the
    count to 3 and the finding lands in the governor inbox — indeterminate +
    human — instead of the abandoned pile."""
    emitter = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    proposal_id = f"test-d10-atcap-{uuid.uuid4().hex[:8]}"
    await _insert_deferred_finding(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        proposal_id=proposal_id,
        subject=_subject(),
        attempt_count=_CAP - 1,
    )
    try:
        revival = (
            await BlackboardService().revive_or_delegate_findings_for_noop_proposal(
                proposal_id=proposal_id,
                reason="nothing to commit",
                remediation_cap_n=_CAP,
            )
        )
        assert revival is not None
        assert revival["delegated_count"] == 1
        assert entry_id in revival["delegated_finding_ids"]
        assert revival["revived_count"] == 0
        row = await _fetch(db_session, entry_id)
        assert row.status == "indeterminate"
        assert row.resolution_mechanism == "human"
        assert row.claimed_by is None and row.resolved_at is None
        assert row.attempt_count == _CAP
        assert row.delegation["reason"] == "noop_cap_delegated"
        assert row.delegation["proposal_id"] == proposal_id
    finally:
        await _cleanup(db_session, entry_id, emitter)


# ID: 9ac30bae-0fb9-4055-abf8-378726a51806
async def test_delegated_finding_survives_sensor_cycles_until_the_violation_clears(
    db_session: AsyncSession,
) -> None:
    """Criterion 10 — the load-bearing invariant, driven through the two real
    sensor-side queries AuditViolationSensor runs every cycle:

    while the violation persists (subject in the sensor's current set), N
    cycles of dedup fetch + ADR-127 drain leave the delegated finding exactly
    where it is and keep its subject in the active set, so the sensor never
    re-posts it; once the violation is gone, the clean-pass drain — the sole
    automated exit — resolves it with system.audit attribution."""
    emitter = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    proposal_id = f"test-d10-inv-{uuid.uuid4().hex[:8]}"
    subject, prefix = _isolated_subject()
    await _insert_deferred_finding(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        proposal_id=proposal_id,
        subject=subject,
        attempt_count=_CAP - 1,
    )
    svc = BlackboardService()
    try:
        await svc.revive_or_delegate_findings_for_noop_proposal(
            proposal_id=proposal_id, reason="nothing to commit", remediation_cap_n=_CAP
        )
        assert (await _fetch(db_session, entry_id)).status == "indeterminate"

        for _cycle in range(5):
            active = await svc.fetch_active_finding_subjects_by_prefix(f"{prefix}%")
            assert subject in active, "sensor would re-post the delegated subject"
            drained = await svc.adjudicate_indeterminate_findings(
                subject_prefix=prefix,
                current_violation_subjects={subject},
                resolved_by="test.adr104.d10",
            )
            assert subject not in drained["resolved_subjects"]
            row = await _fetch(db_session, entry_id)
            assert row.status == "indeterminate"
            assert row.resolution_mechanism == "human"

        drained = await svc.adjudicate_indeterminate_findings(
            subject_prefix=prefix,
            current_violation_subjects=set(),
            resolved_by="test.adr104.d10",
        )
        assert subject in drained["resolved_subjects"]
        row = await _fetch(db_session, entry_id)
        assert row.status == "resolved" and row.resolved_at is not None
        active = await svc.fetch_active_finding_subjects_by_prefix(f"{prefix}%")
        assert subject not in active
    finally:
        await _cleanup(db_session, entry_id, emitter)
