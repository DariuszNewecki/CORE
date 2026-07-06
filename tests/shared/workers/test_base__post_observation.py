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

from shared.workers.base import Worker
from shared.workers.blackboard_publisher import _TERMINAL_STATUSES


pytestmark = [pytest.mark.integration]


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


async def _delete_entry(
    db_session: AsyncSession,
    entry_id: uuid.UUID,
    worker_uuid: uuid.UUID | None = None,
) -> None:
    """Delete the synthetic entry and (if given) the synthetic
    worker_registry row the test inserted. Blackboard first to satisfy
    the FK; registry DELETE is guarded by worker_name so it can never
    reach a live worker.
    """
    await db_session.execute(
        text("delete from core.blackboard_entries where id = :id"),
        {"id": entry_id},
    )
    if worker_uuid is not None:
        await db_session.execute(
            text(
                """
                delete from core.worker_registry
                 where worker_uuid = :worker_uuid
                   and worker_name = 'test.post_observation.synthetic'
                """
            ),
            {"worker_uuid": worker_uuid},
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
    worker._blackboard._worker_uuid = worker._worker_uuid
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
        await _delete_entry(db_session, entry_id, worker._worker_uuid)


# ID: 6f139c4b-a67d-42b4-941e-c90fb2343c3f
async def test_indeterminate_dedup_blocks_duplicate_post(
    db_session: AsyncSession,
) -> None:
    """Known-violating fixture: a second post_observation(status='indeterminate')
    for the same subject raises ValueError. Fails loudly if the guard in
    BlackboardPublisher.post_observation is removed or bypassed.
    """
    worker = _ObservationMinimalWorker()
    worker._worker_uuid = uuid.uuid4()
    worker._blackboard._worker_uuid = worker._worker_uuid
    await _ensure_worker_registered(db_session, worker._worker_uuid)

    subject = f"test.indeterminate.dedup.violating::{uuid.uuid4()}"
    entry_id = await worker.post_observation(
        subject=subject, payload={"cycle": 1}, status="indeterminate"
    )
    try:
        with pytest.raises(ValueError, match="duplicate indeterminate"):
            await worker.post_observation(
                subject=subject, payload={"cycle": 2}, status="indeterminate"
            )
    finally:
        await _delete_entry(db_session, entry_id, worker._worker_uuid)


# ID: b7c7f2b6-f0e0-4549-a056-51ce6e47ff07
async def test_indeterminate_dedup_permits_repost_after_governor_resolve(
    db_session: AsyncSession,
) -> None:
    """Known-compliant fixture: post indeterminate → governor resolves →
    re-post succeeds with exactly 2 rows. Mirrors the canonical detection
    lifecycle: detect → governor closes → re-detect is valid.
    """
    from sqlalchemy import text as sa_text

    worker = _ObservationMinimalWorker()
    worker._worker_uuid = uuid.uuid4()
    worker._blackboard._worker_uuid = worker._worker_uuid
    await _ensure_worker_registered(db_session, worker._worker_uuid)

    subject = f"test.indeterminate.dedup.compliant::{uuid.uuid4()}"
    entry_id_1 = await worker.post_observation(
        subject=subject, payload={"cycle": 1}, status="indeterminate"
    )

    # Simulate governor resolving the finding (mirrors: core-admin blackboard resolve)
    await db_session.execute(
        sa_text(
            "UPDATE core.blackboard_entries "
            "SET status = 'resolved', resolved_at = now() "
            "WHERE id = :id"
        ),
        {"id": entry_id_1},
    )
    await db_session.commit()

    # Re-detection: prior indeterminate is resolved; dedup guard passes
    entry_id_2 = await worker.post_observation(
        subject=subject, payload={"cycle": 2}, status="indeterminate"
    )
    try:
        db_session.expire_all()
        result = await db_session.execute(
            sa_text(
                "SELECT COUNT(*) FROM core.blackboard_entries WHERE subject = :subject"
            ),
            {"subject": subject},
        )
        count = result.scalar()
        assert count == 2, f"Expected 2 rows for {subject!r}, got {count}"
    finally:
        await db_session.execute(
            sa_text(
                "DELETE FROM core.blackboard_entries WHERE subject = :subject"
            ),
            {"subject": subject},
        )
        await db_session.execute(
            sa_text(
                "DELETE FROM core.worker_registry "
                "WHERE worker_uuid = :worker_uuid "
                "  AND worker_name = 'test.post_observation.synthetic'"
            ),
            {"worker_uuid": worker._worker_uuid},
        )
        await db_session.commit()


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
