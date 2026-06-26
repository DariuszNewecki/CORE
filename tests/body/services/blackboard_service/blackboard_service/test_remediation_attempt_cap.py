"""Integration tests for ADR-104 D9 (#637) — the remediation-attempt cap on
``BlackboardService.revive_findings_for_failed_proposal``.

The D3 orphan abandon-at-cap principle, applied one trigger over: a finding
revived from a failed proposal counts its attempts in
``payload.remediation_attempt_count``; when ``remediation_cap_n`` is supplied
and this failure makes the count reach the cap, the finding is abandoned
(terminal Type-B) instead of routed back to awaiting_reaudit — breaking the
generate -> fail -> revive -> regenerate loop on a perpetually-failing
remediation. These tests exercise the acceptance cases (ADR-104 D9 criterion 7)
against the live test DB:

  * below the cap: revived to awaiting_reaudit, count incremented, claim
    markers cleared (the pre-#637 behaviour, now also counting);
  * at the cap: abandoned (terminal, resolved_at set), count incremented,
    surfaced in the abandoned set so the worker can post the terminal
    blackboard.remediation_cap_reached observation;
  * uncapped path (remediation_cap_n=None, the governor-reject caller):
    revived without touching the counter — a human decision is not a
    remediation failure and must not count toward auto-abandon.

Synthetic UUIDs + self-cleanup, same pattern as the ADR-104 D3
release_orphaned_claims tests.
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

_SYNTH_NAME = "test.adr104.d9.synthetic"
_CAP = 3


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """Prime the service registry so BlackboardService's internal
    ServiceRegistry.session() resolves a live session — mirrors the
    production entry-point bootstrap and the test_reject_revives_findings
    fixture. Required when this file runs in isolation (nothing else has
    primed the singleton yet)."""
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
    attempt_count: int | None = None,
) -> None:
    """Seed a finding parked at deferred_to_proposal for ``proposal_id`` with
    resolution_mechanism='reaudit' (the revival guard), mirroring the §7
    transition ViolationRemediatorWorker._defer_to_proposal performs."""
    await _register_worker(db_session, worker_uuid)
    payload: dict[str, object] = {
        "file_path": "src/foo.py",
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
                 'deferred_to_proposal',
                 'audit.violation::workflow.ruff_format_check',
                 cast(:payload as jsonb), 'reaudit',
                 :worker_uuid, now(), now())
            """
        ),
        {
            "id": entry_id,
            "worker_uuid": worker_uuid,
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
                   claimed_by,
                   resolved_at,
                   (payload->>'remediation_attempt_count')::int as attempt_count
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
            """
            delete from core.worker_registry
             where worker_uuid = :u and worker_name = :n
            """
        ),
        {"u": worker_uuid, "n": _SYNTH_NAME},
    )
    await db_session.commit()


# ID: b7e09674-905b-45a5-b8a2-abc653468af4
async def test_below_cap_revives_and_increments(db_session: AsyncSession) -> None:
    """A finding well below the cap is revived to awaiting_reaudit with claim
    markers cleared and its attempt count incremented — the pre-#637 revival,
    now also counting. With cap=3 and a prior count of 0, this failure takes
    the count to 1 and revives."""
    emitter = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    proposal_id = f"test-d9-below-{uuid.uuid4().hex[:8]}"
    await _insert_deferred_finding(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        proposal_id=proposal_id,
        attempt_count=0,
    )
    try:
        revival = await BlackboardService().revive_findings_for_failed_proposal(
            proposal_id=proposal_id,
            failure_reason="sandbox gate failed",
            remediation_cap_n=_CAP,
        )
        assert revival is not None
        assert revival["revived_count"] == 1
        assert entry_id in revival["revived_finding_ids"]
        assert revival["abandoned_count"] == 0
        row = await _fetch(db_session, entry_id)
        assert row.status == "awaiting_reaudit"
        assert row.claimed_by is None
        assert row.resolved_at is None
        assert row.attempt_count == 1
    finally:
        await _cleanup(db_session, entry_id, emitter)


# ID: 6da1a5a5-cfbb-4028-9e1e-7be72b87f4ed
async def test_at_cap_abandons(db_session: AsyncSession) -> None:
    """A finding whose next failure reaches the cap is abandoned (terminal,
    resolved_at set) instead of revived — the ADR-104 D9 rail that breaks the
    generate -> fail -> revive loop. With cap=3 and a prior count of 2, this
    failure takes the count to 3 and abandons; the entry surfaces in the
    abandoned set so the worker posts the terminal observation (D4)."""
    emitter = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    proposal_id = f"test-d9-atcap-{uuid.uuid4().hex[:8]}"
    await _insert_deferred_finding(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        proposal_id=proposal_id,
        attempt_count=_CAP - 1,
    )
    try:
        revival = await BlackboardService().revive_findings_for_failed_proposal(
            proposal_id=proposal_id,
            failure_reason="sandbox gate failed (cap)",
            remediation_cap_n=_CAP,
        )
        assert revival is not None
        assert revival["abandoned_count"] == 1
        assert entry_id in revival["abandoned_finding_ids"]
        assert revival["revived_count"] == 0
        row = await _fetch(db_session, entry_id)
        assert row.status == "abandoned"
        assert row.resolved_at is not None
        assert row.attempt_count == _CAP
    finally:
        await _cleanup(db_session, entry_id, emitter)


# ID: 6bbe6f3b-e9be-4148-94ec-ee485f640dfb
async def test_uncapped_path_revives_without_counting(
    db_session: AsyncSession,
) -> None:
    """The governor-reject path passes no cap (remediation_cap_n=None): the
    finding is revived to awaiting_reaudit exactly as pre-#637, and the attempt
    counter is left untouched — a human decision must not count toward
    auto-abandon. Seeded with no counter at all to prove the uncapped path
    neither requires nor writes it."""
    emitter = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    proposal_id = f"test-d9-uncapped-{uuid.uuid4().hex[:8]}"
    await _insert_deferred_finding(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        proposal_id=proposal_id,
        attempt_count=None,
    )
    try:
        revival = await BlackboardService().revive_findings_for_failed_proposal(
            proposal_id=proposal_id,
            failure_reason="rejected: governor override",
        )
        assert revival is not None
        assert revival["revived_count"] == 1
        assert revival["abandoned_count"] == 0
        row = await _fetch(db_session, entry_id)
        assert row.status == "awaiting_reaudit"
        assert row.claimed_by is None
        assert row.attempt_count is None
    finally:
        await _cleanup(db_session, entry_id, emitter)
