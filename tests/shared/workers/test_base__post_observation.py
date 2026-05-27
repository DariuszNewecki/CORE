"""Tests for Worker.post_observation — the terminal-at-creation entry path
for observability findings.

Established 2026-05-25 after live recon showed observability-class findings
(sync.db.failed, autonomy.yielded.scope_collision, governance.edge5.orphan_sha,
audit.remediation.dry_run, worker.silent) were being posted via post_finding
with status='open'. None of those subjects have a worker that claims and
resolves them, so they aged past SLA, BlackboardShopManager generated
stale-alerts, and both classes accumulated forever (5,946 historical rows
cleared in the Phase 1 purge that surfaced this).

post_observation requires the caller to pick a terminal status explicitly,
since the semantic choice is meaningful per .intent/META/enums.json
(abandoned vs indeterminate vs dry_run_complete vs suppressed).
"""

from __future__ import annotations

import uuid
from typing import ClassVar

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.workers.base import _TERMINAL_STATUSES, Worker


class _ObservationMinimalWorker(Worker):
    """Test-only Worker that loads a real declaration to satisfy
    Worker.__init__, but its UUID is monkeypatched in each test so the
    INSERTs and reads target test-unique rows only.
    """

    declaration_name: ClassVar[str] = "db_sync_worker"

    async def run(self) -> None:
        return


async def _ensure_worker_registered(
    db_session: AsyncSession, worker_uuid: uuid.UUID
) -> None:
    await db_session.execute(
        text(
            """
            insert into core.worker_registry
                (worker_uuid, worker_name, worker_class, phase, last_heartbeat)
            values
                (:worker_uuid, 'test.post_observation.synthetic', 'test', 'audit', now())
            on conflict (worker_uuid) do nothing
            """
        ),
        {"worker_uuid": worker_uuid},
    )
    await db_session.commit()


async def _fetch_entry(
    db_session: AsyncSession, entry_id: uuid.UUID
) -> tuple[str, str, str]:
    db_session.expire_all()
    result = await db_session.execute(
        text(
            "select entry_type, status, subject from core.blackboard_entries "
            "where id = :id"
        ),
        {"id": entry_id},
    )
    row = result.one()
    return (row.entry_type, row.status, row.subject)


async def _delete_entry(db_session: AsyncSession, entry_id: uuid.UUID) -> None:
    await db_session.execute(
        text("delete from core.blackboard_entries where id = :id"),
        {"id": entry_id},
    )
    await db_session.commit()


# ID: d3f85215-3e1a-4364-9920-ff8e26fd6a9a
async def test_post_observation_rejects_non_terminal_status() -> None:
    """status='open' is the non-terminal default for post_finding — passing
    it to post_observation is the exact mistake the API is designed to prevent.
    """
    worker = _ObservationMinimalWorker()
    with pytest.raises(ValueError, match="requires a terminal status"):
        await worker.post_observation(
            subject="test.post_observation.invalid",
            payload={},
            status="open",
        )


# ID: 154e0292-cfd7-4d90-8b48-0bf0cb0369e8
async def test_post_observation_rejects_arbitrary_string() -> None:
    """The validator must enforce the terminal-status enum, not just any
    non-'open' string, otherwise typos slip past silently."""
    worker = _ObservationMinimalWorker()
    with pytest.raises(ValueError, match="requires a terminal status"):
        await worker.post_observation(
            subject="test.post_observation.invalid",
            payload={},
            status="not_a_real_status",
        )


# ID: 7571ed95-4b26-443e-b59e-d59032b43f57
async def test_post_observation_writes_with_terminal_status(
    db_session: AsyncSession,
) -> None:
    """Integration: the row lands with entry_type='finding' and the
    requested terminal status. Uses 'abandoned' as a representative —
    it's the status three of the five real emitters pick.
    """
    worker = _ObservationMinimalWorker()
    worker._worker_uuid = uuid.uuid4()
    await _ensure_worker_registered(db_session, worker._worker_uuid)

    entry_id = await worker.post_observation(
        subject="test.post_observation.synthetic",
        payload={"smoke": True},
        status="abandoned",
    )
    try:
        entry_type, status, subject = await _fetch_entry(db_session, entry_id)
        assert entry_type == "finding"
        assert status == "abandoned"
        assert subject == "test.post_observation.synthetic"
    finally:
        await _delete_entry(db_session, entry_id)


def test_terminal_statuses_match_enums_taxonomy() -> None:
    """The terminal-status set MUST match .intent/META/enums.json
    blackboard_entry_status terminal subset. Drift here defeats the
    constitutional grounding of the contract.
    """
    expected = {
        "resolved",
        "abandoned",
        "suppressed",
        "dry_run_complete",
        "indeterminate",
        "deferred_to_proposal",
    }
    assert _TERMINAL_STATUSES == expected
