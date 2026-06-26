"""Integration tests for ADR-104 — BlackboardService.release_orphaned_claims.

The orphaned-claim reaper releases claims held by workers that are provably
gone (claimed_by not in the alive-set, claimed_at past the grace window) and
abandons an entry once its orphan_release_count reaches the reclaim cap (D3).
These tests exercise the acceptance cases against the live test DB:

  * a dead-owner claim past grace IS released (count incremented);
  * a claim held by a live uuid is NOT released;
  * a claim still within the grace window is NOT released;
  * an empty alive-set reaps nothing (D5 defense-in-depth);
  * an entry one reap below the cap is abandoned (terminal), not re-opened.

Synthetic UUIDs + self-cleanup, same pattern as the ADR-069 D8 tests.
Requires the orphan_release_count column (ADR-104 schema change).
"""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.blackboard_service.blackboard_service import BlackboardService

pytestmark = [pytest.mark.integration]

_SYNTH_NAME = "test.adr104.synthetic"
_GRACE = 600
_CAP = 3


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


async def _insert_claimed(
    db_session: AsyncSession,
    *,
    entry_id: str,
    worker_uuid: uuid.UUID,
    claimed_by: uuid.UUID,
    claimed_age_sec: int,
    orphan_release_count: int = 0,
) -> None:
    # Only worker_uuid carries an FK to worker_registry; claimed_by does not.
    await _register_worker(db_session, worker_uuid)
    await db_session.execute(
        text(
            """
            insert into core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject, payload,
                 resolution_mechanism, claimed_by, claimed_at,
                 orphan_release_count)
            values
                (cast(:id as uuid), :worker_uuid, 'finding', 'audit', 'claimed',
                 :subject, cast('{}' as jsonb), 'human', :claimed_by,
                 now() - make_interval(secs => :age), :orc)
            """
        ),
        {
            "id": entry_id,
            "worker_uuid": worker_uuid,
            "subject": _SYNTH_NAME,
            "claimed_by": claimed_by,
            "age": claimed_age_sec,
            "orc": orphan_release_count,
        },
    )
    await db_session.commit()


async def _fetch(db_session: AsyncSession, entry_id: str):
    db_session.expire_all()
    result = await db_session.execute(
        text(
            """
            select status, claimed_by, orphan_release_count, resolved_at
              from core.blackboard_entries
             where id = cast(:id as uuid)
            """
        ),
        {"id": entry_id},
    )
    return result.one()


async def _cleanup(
    db_session: AsyncSession, entry_id: str, *worker_uuids: uuid.UUID
) -> None:
    await db_session.execute(
        text("delete from core.blackboard_entries where id = cast(:id as uuid)"),
        {"id": entry_id},
    )
    for worker_uuid in worker_uuids:
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


# ID: dc587858-f235-40cc-810c-9db9b3fe889d
async def test_dead_owner_past_grace_is_released(db_session: AsyncSession) -> None:
    """A claim whose owner is not alive and whose claimed_at is past grace is
    reset to open with claimed_by cleared and the reap counter incremented."""
    emitter = uuid.uuid4()
    dead_owner = uuid.uuid4()
    live_owner = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    await _insert_claimed(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        claimed_by=dead_owner,
        claimed_age_sec=_GRACE + 100,
    )
    try:
        result = await BlackboardService().release_orphaned_claims(
            live_uuids=[str(live_owner)],
            grace_seconds=_GRACE,
            reclaim_cap_n=_CAP,
            batch_max=500,
        )
        assert entry_id in result["released"]
        assert entry_id not in result["abandoned"]
        row = await _fetch(db_session, entry_id)
        assert row.status == "open"
        assert row.claimed_by is None
        assert row.orphan_release_count == 1
    finally:
        await _cleanup(db_session, entry_id, emitter)


# ID: d01cb9fa-c6de-478f-96d9-a6096e770c38
async def test_live_owner_not_released(db_session: AsyncSession) -> None:
    """A claim held by a uuid in the alive-set is never reaped — the safety
    invariant (ADR-104 D1 condition 3)."""
    emitter = uuid.uuid4()
    live_owner = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    await _insert_claimed(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        claimed_by=live_owner,
        claimed_age_sec=_GRACE + 100,
    )
    try:
        result = await BlackboardService().release_orphaned_claims(
            live_uuids=[str(live_owner)],
            grace_seconds=_GRACE,
            reclaim_cap_n=_CAP,
            batch_max=500,
        )
        assert result["released"] == []
        assert result["abandoned"] == []
        row = await _fetch(db_session, entry_id)
        assert row.status == "claimed"
        assert row.claimed_by == live_owner
        assert row.orphan_release_count == 0
    finally:
        await _cleanup(db_session, entry_id, emitter)


# ID: 8d1b7836-2302-4096-98c4-43087c0580e6
async def test_within_grace_not_released(db_session: AsyncSession) -> None:
    """A freshly-claimed entry (within the grace window) is left alone even
    when its owner is not in the alive-set — the grace protects a worker that
    has not yet emitted its run-start heartbeat."""
    emitter = uuid.uuid4()
    dead_owner = uuid.uuid4()
    other_live = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    await _insert_claimed(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        claimed_by=dead_owner,
        claimed_age_sec=30,
    )
    try:
        result = await BlackboardService().release_orphaned_claims(
            live_uuids=[str(other_live)],
            grace_seconds=_GRACE,
            reclaim_cap_n=_CAP,
            batch_max=500,
        )
        assert entry_id not in result["released"]
        assert entry_id not in result["abandoned"]
        row = await _fetch(db_session, entry_id)
        assert row.status == "claimed"
    finally:
        await _cleanup(db_session, entry_id, emitter)


# ID: cedd2686-555f-4e3b-a098-7902f8a8c6be
async def test_empty_alive_set_reaps_nothing(db_session: AsyncSession) -> None:
    """An empty alive-set must reap nothing — without this guard, a transient
    registry glitch would mass-release every claim (ADR-104 D5)."""
    emitter = uuid.uuid4()
    dead_owner = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    await _insert_claimed(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        claimed_by=dead_owner,
        claimed_age_sec=_GRACE + 100,
    )
    try:
        result = await BlackboardService().release_orphaned_claims(
            live_uuids=[],
            grace_seconds=_GRACE,
            reclaim_cap_n=_CAP,
            batch_max=500,
        )
        assert result == {"released": [], "abandoned": []}
        row = await _fetch(db_session, entry_id)
        assert row.status == "claimed"
    finally:
        await _cleanup(db_session, entry_id, emitter)


# ID: 5afc0937-37e1-4e2e-b9c7-82ec182bb518
async def test_entry_at_reclaim_cap_is_abandoned(db_session: AsyncSession) -> None:
    """An orphan whose next reap reaches the reclaim cap is abandoned
    (terminal, resolved_at set) instead of re-opened — the ADR-104 D3 rail
    that breaks a crash -> reclaim -> crash loop. With cap=3 and a prior count
    of 2, this reap takes the count to 3 and abandons."""
    emitter = uuid.uuid4()
    dead_owner = uuid.uuid4()
    live_owner = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    await _insert_claimed(
        db_session,
        entry_id=entry_id,
        worker_uuid=emitter,
        claimed_by=dead_owner,
        claimed_age_sec=_GRACE + 100,
        orphan_release_count=_CAP - 1,
    )
    try:
        result = await BlackboardService().release_orphaned_claims(
            live_uuids=[str(live_owner)],
            grace_seconds=_GRACE,
            reclaim_cap_n=_CAP,
            batch_max=500,
        )
        assert entry_id in result["abandoned"]
        assert entry_id not in result["released"]
        row = await _fetch(db_session, entry_id)
        assert row.status == "abandoned"
        assert row.resolved_at is not None
        assert row.orphan_release_count == _CAP
    finally:
        await _cleanup(db_session, entry_id, emitter)
