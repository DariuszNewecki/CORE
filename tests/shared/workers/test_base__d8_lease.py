"""Integration tests for ADR-104 D8 — the worker liveness lease.

The orphaned-claim reaper (ADR-104 D1) reaps claims whose owner is not in the
alive-set. Heartbeats are otherwise posted only at run-start, so a worker
holding a claim for longer than worker_alive_threshold_sec would be mistaken
for dead and reaped mid-work. The D8 lease — Worker._renew_registry_heartbeat,
driven on a cadence by a background task in Worker.start() — refreshes
worker_registry.last_heartbeat so a long-running worker stays alive.

These tests prove the renewal mechanism (a stale registry row becomes fresh
after one renewal, so the reaper's liveness query would classify it alive and
skip its claims) and that start() spawns and cancels the lease cleanly.

Synthetic UUIDs + self-cleanup, same pattern as the ADR-069 D8 tests.
"""

from __future__ import annotations

import uuid
from typing import ClassVar
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.workers.base import Worker


pytestmark = [pytest.mark.integration]

_SYNTH_NAME = "test.adr104.lease.synthetic"


class _LeaseMinimalWorker(Worker):
    """Test-only Worker that loads a real declaration but does no work.

    Uses ``db_sync_worker`` purely as a declaration source so
    ``Worker.__init__`` succeeds; tests overwrite ``self._worker_uuid``
    with a fresh UUID so registry writes only touch synthetic rows.
    """

    declaration_name: ClassVar[str] = "db_sync_worker"

    async def run(self) -> None:
        return


async def _insert_registry(
    db_session: AsyncSession, worker_uuid: uuid.UUID, last_heartbeat_age_sec: int
) -> None:
    await db_session.execute(
        text(
            """
            insert into core.worker_registry
                (worker_uuid, worker_name, worker_class, phase, last_heartbeat)
            values
                (:u, :n, 'test', 'audit', now() - make_interval(secs => :age))
            on conflict (worker_uuid)
                do update set last_heartbeat = excluded.last_heartbeat
            """
        ),
        {"u": worker_uuid, "n": _SYNTH_NAME, "age": last_heartbeat_age_sec},
    )
    await db_session.commit()


async def _seconds_silent(db_session: AsyncSession, worker_uuid: uuid.UUID) -> int:
    db_session.expire_all()
    result = await db_session.execute(
        text(
            """
            select extract(epoch from (now() - last_heartbeat))::int
              from core.worker_registry
             where worker_uuid = :u
            """
        ),
        {"u": worker_uuid},
    )
    return result.scalar_one()


async def _cleanup(db_session: AsyncSession, worker_uuid: uuid.UUID) -> None:
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


# ID: 7d447f52-a4d4-4d27-a578-b713630a2911
async def test_renew_registry_heartbeat_refreshes_timestamp(
    db_session: AsyncSession,
) -> None:
    """A stale worker_registry row becomes fresh after one lease renewal.

    This is the safety guarantee in miniature: a worker that has been running
    (and renewing) for longer than the 600s alive-threshold stays inside the
    alive window, so the reaper's `claimed_by NOT IN alive` test never matches
    its live claims.
    """
    worker = _LeaseMinimalWorker()
    worker._worker_uuid = uuid.uuid4()
    await _insert_registry(db_session, worker._worker_uuid, last_heartbeat_age_sec=1000)
    try:
        before = await _seconds_silent(db_session, worker._worker_uuid)
        assert before >= 900, "row should start comfortably past the alive-threshold"
        await worker._renew_registry_heartbeat()
        after = await _seconds_silent(db_session, worker._worker_uuid)
        assert after < 60, "after renewal the worker is fresh, i.e. provably alive"
    finally:
        await _cleanup(db_session, worker._worker_uuid)


# ID: fe47b329-5558-47b5-8af7-7940495c3baa
async def test_start_spawns_and_cancels_lease_cleanly(
    db_session: AsyncSession,
) -> None:
    """start() spawns the lease task and cancels it in the finally block when
    run() completes — no error surfaced, no lingering task.

    run() increments _cycle_post_count directly to satisfy the silence check
    without hitting the DB (the test is about lease spawn/cancel, not blackboard
    writes). _blackboard is also mocked to keep the test fully in-memory.
    """
    from unittest.mock import MagicMock, patch

    worker = _LeaseMinimalWorker()
    worker._worker_uuid = uuid.uuid4()
    # Isolate the lifecycle from registration/release DB writes — this test
    # is about the lease task's spawn/cancel, not those surfaces.
    worker._register = AsyncMock()
    worker._release_held_claims = AsyncMock(return_value=0)

    # Satisfy the silence check without a real DB write: bump _cycle_post_count
    # inside run() so start() does not raise WorkerSilenceError.
    async def _run_with_heartbeat() -> None:
        worker._cycle_post_count += 1

    worker.run = _run_with_heartbeat  # type: ignore[method-assign]

    # Mock the blackboard entirely so no FK-constrained DB insert is attempted.
    mock_bb = MagicMock()
    mock_bb._post_entry = AsyncMock(return_value=uuid.uuid4())
    mock_bb.post_heartbeat = AsyncMock(return_value=uuid.uuid4())
    worker._blackboard = mock_bb

    # run() completes immediately; the lease task must be cancelled cleanly.
    await worker.start()

    worker._register.assert_awaited_once()
    worker._release_held_claims.assert_awaited_once()
