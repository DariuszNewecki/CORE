"""Integration tests for ADR-069 D8 — graceful shutdown pre-release of claims.

Closes the orphan-claim window that #439's 2026-05-25 evidence demonstrated:
a clean ``systemctl stop`` leaves rows in ``status='claimed'`` if a worker
was mid-claim at the SIGTERM moment and didn't run its terminal transition.
The release-on-exit hook in ``Worker.start()``'s finally block — backed by
``Worker._release_held_claims`` — ensures held entries return to
``status='open'`` even on ``asyncio.CancelledError`` propagation.

These tests use the live test database via the conftest ``db_session``
fixture and clean up after themselves. They patch ``self._worker_uuid``
to a test-unique UUID after instantiation so the WHERE-clause never
matches a live worker's claims.
"""

from __future__ import annotations

import asyncio
import uuid
from typing import ClassVar
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.workers.base import Worker


class _D8MinimalWorker(Worker):
    """Test-only Worker that loads a real declaration but never claims.

    Uses ``db_sync_worker`` purely as a declaration source so
    ``Worker.__init__`` succeeds. Tests overwrite ``self._worker_uuid``
    immediately after construction with a fresh UUID so the release SQL
    only matches rows the test itself inserted.
    """

    declaration_name: ClassVar[str] = "db_sync_worker"

    async def run(self) -> None:
        return


async def _ensure_worker_registered(
    db_session: AsyncSession, worker_uuid: uuid.UUID
) -> None:
    """Insert a worker_registry row for a synthetic UUID.

    Required because blackboard_entries.worker_uuid carries an FK to
    worker_registry.worker_uuid. ON CONFLICT DO NOTHING keeps the helper
    safe to call for both emitter and claimer (which may be the same UUID).
    """
    await db_session.execute(
        text(
            """
            insert into core.worker_registry
                (worker_uuid, worker_name, worker_class, phase, last_heartbeat)
            values
                (:worker_uuid, 'test.d8.synthetic', 'test', 'audit', now())
            on conflict (worker_uuid) do nothing
            """
        ),
        {"worker_uuid": worker_uuid},
    )
    await db_session.commit()


async def _insert_synthetic_claimed_entry(
    db_session: AsyncSession,
    *,
    entry_id: str,
    worker_uuid: uuid.UUID,
    claimed_by: uuid.UUID,
) -> None:
    await _ensure_worker_registered(db_session, worker_uuid)
    if claimed_by != worker_uuid:
        await _ensure_worker_registered(db_session, claimed_by)
    await db_session.execute(
        text(
            """
            insert into core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject, payload,
                 claimed_by, claimed_at)
            values
                (cast(:id as uuid), :worker_uuid, 'finding', 'audit',
                 'claimed', 'test.d8.synthetic', cast('{}' as jsonb),
                 :claimed_by, now())
            """
        ),
        {
            "id": entry_id,
            "worker_uuid": worker_uuid,
            "claimed_by": claimed_by,
        },
    )
    await db_session.commit()


async def _fetch_entry_status(
    db_session: AsyncSession, entry_id: str
) -> tuple[str, uuid.UUID | None]:
    db_session.expire_all()
    result = await db_session.execute(
        text(
            """
            select status, claimed_by
              from core.blackboard_entries
             where id = cast(:id as uuid)
            """
        ),
        {"id": entry_id},
    )
    row = result.one()
    return (row.status, row.claimed_by)


async def _delete_entry(db_session: AsyncSession, entry_id: str) -> None:
    """Delete the synthetic entry. Leaves the worker_registry rows alone —
    they're harmless test markers with worker_name='test.d8.synthetic' and
    are cheaper to leave than to cascade-clean (FK from blackboard_entries
    would block deletion anyway if other rows still reference them).
    """
    await db_session.execute(
        text("delete from core.blackboard_entries where id = cast(:id as uuid)"),
        {"id": entry_id},
    )
    await db_session.commit()


# ID: 2c4e2462-7d40-4854-a315-dfaece55cb15
async def test_release_held_claims_releases_my_held_entries(
    db_session: AsyncSession,
) -> None:
    """A claimed entry whose claimed_by matches the worker UUID is released."""
    worker = _D8MinimalWorker()
    worker._worker_uuid = uuid.uuid4()
    entry_id = str(uuid.uuid4())
    await _insert_synthetic_claimed_entry(
        db_session,
        entry_id=entry_id,
        worker_uuid=worker._worker_uuid,
        claimed_by=worker._worker_uuid,
    )
    try:
        released = await worker._release_held_claims()
        assert released == 1, (
            f"_release_held_claims should release the 1 synthetic entry, got {released}"
        )
        status, claimed_by = await _fetch_entry_status(db_session, entry_id)
        assert status == "open"
        assert claimed_by is None
    finally:
        await _delete_entry(db_session, entry_id)


# ID: 072ff400-79e2-4721-956d-867c0e126767
async def test_release_held_claims_skips_other_workers_claims(
    db_session: AsyncSession,
) -> None:
    """Release is selective — entries claimed by another worker are untouched."""
    worker = _D8MinimalWorker()
    worker._worker_uuid = uuid.uuid4()
    other_worker_uuid = uuid.uuid4()
    other_entry_id = str(uuid.uuid4())
    await _insert_synthetic_claimed_entry(
        db_session,
        entry_id=other_entry_id,
        worker_uuid=other_worker_uuid,
        claimed_by=other_worker_uuid,
    )
    try:
        released = await worker._release_held_claims()
        assert released == 0
        status, claimed_by = await _fetch_entry_status(db_session, other_entry_id)
        assert status == "claimed"
        assert claimed_by == other_worker_uuid
    finally:
        await _delete_entry(db_session, other_entry_id)


# ID: 318b9d91-fc43-4880-8552-ecf962603b8b
async def test_start_releases_claims_on_cancellation(
    db_session: AsyncSession,
) -> None:
    """End-to-end: start()'s finally block releases held claims when
    run() raises asyncio.CancelledError — the graceful-shutdown path
    that #439's evidence demonstrated leaks claims today.
    """

    class _CancellingWorker(_D8MinimalWorker):
        async def run(self) -> None:
            raise asyncio.CancelledError()

    worker = _CancellingWorker()
    worker._worker_uuid = uuid.uuid4()
    # Skip worker_registry write — this test is about the claim-release
    # contract, not the registration lifecycle.
    worker._register = AsyncMock()

    entry_id = str(uuid.uuid4())
    await _insert_synthetic_claimed_entry(
        db_session,
        entry_id=entry_id,
        worker_uuid=worker._worker_uuid,
        claimed_by=worker._worker_uuid,
    )
    try:
        with pytest.raises(asyncio.CancelledError):
            await worker.start()
        status, claimed_by = await _fetch_entry_status(db_session, entry_id)
        assert status == "open"
        assert claimed_by is None
    finally:
        await _delete_entry(db_session, entry_id)
