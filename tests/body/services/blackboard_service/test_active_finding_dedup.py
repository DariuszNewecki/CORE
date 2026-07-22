# tests/body/services/blackboard_service/test_active_finding_dedup.py

"""Active-finding dedup + recovered-target resolver — the blackboard ledger defect.

Integration tests against a real Postgres carrying the ``uq_active_finding_identity``
partial unique index (schema.sql). They verify:

- a non-terminal finding is unique per canonical identity
  (subject, resolution_mechanism): a second post of the same standing finding
  UPSERTS one row (occurrence_count += 1, payload = latest, first_payload
  retained) instead of manufacturing a duplicate open row;
- concurrent posters collapse to one row (DB-enforced, race-proof);
- distinct resolution_mechanism is a distinct identity;
- the stale-alert resolver closes an alert whose target is terminal, missing,
  or recovered (re-observed within the SLA window), and keeps it while the
  target is non-terminal AND still stale.
"""

from __future__ import annotations

import asyncio
import json
import uuid

import pytest
from sqlalchemy import text

from body.services.blackboard_service.blackboard_service import BlackboardService
from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session
from shared.workers.blackboard_publisher import BlackboardPublisher


pytestmark = pytest.mark.integration


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    """The resolver opens its own session via ServiceRegistry.session(); bind it
    to the test DB session factory (not initialized in a bare pytest)."""
    service_registry.prime(get_session)


def _publisher(worker_uuid: uuid.UUID) -> BlackboardPublisher:
    return BlackboardPublisher(
        worker_uuid=worker_uuid,
        worker_name="test_dedup_worker",
        phase="audit",
        declaration={},
    )


async def _count_active(session, subject: str, mech: str) -> int:
    r = await session.execute(
        text(
            """
            SELECT count(*) FROM core.blackboard_entries
            WHERE entry_type='finding'
              AND status IN ('open','claimed','awaiting_reaudit')
              AND subject=:s AND resolution_mechanism=:m
            """
        ),
        {"s": subject, "m": mech},
    )
    return r.scalar_one()


async def _insert_finding(
    session, worker_uuid, subject, status, mech, age_sec=0, payload=None
) -> uuid.UUID:
    fid = uuid.uuid4()
    await session.execute(
        text(
            """
            INSERT INTO core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject, payload,
                 resolution_mechanism, resolved_at, created_at, updated_at, last_seen_at)
            VALUES
                (:i, :w, 'finding', 'audit', :st, :s, cast(:p as jsonb), :m,
                 CASE WHEN :st IN ('resolved','abandoned','indeterminate') THEN now() ELSE null END,
                 now() - (:age * interval '1 second'),
                 now() - (:age * interval '1 second'),
                 now() - (:age * interval '1 second'))
            """
        ),
        {
            "i": fid,
            "w": worker_uuid,
            "st": status,
            "s": subject,
            "p": json.dumps(payload or {}),
            "m": mech,
            "age": age_sec,
        },
    )
    return fid


async def _status(session, entry_id) -> str:
    r = await session.execute(
        text("SELECT status FROM core.blackboard_entries WHERE id=:i"), {"i": entry_id}
    )
    return r.scalar_one()


@pytest.fixture
async def worker_id():
    wid = uuid.uuid4()
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    INSERT INTO core.worker_registry
                        (worker_uuid, worker_name, worker_class, phase)
                    VALUES (:w, 'test_dedup_worker', 'supervision', 'audit')
                    """
                ),
                {"w": wid},
            )
    yield wid
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text("DELETE FROM core.blackboard_entries WHERE worker_uuid=:w"),
                {"w": wid},
            )
            await session.execute(
                text("DELETE FROM core.worker_registry WHERE worker_uuid=:w"),
                {"w": wid},
            )


async def test_repeat_post_dedups_to_one_row(worker_id):
    subject = f"test.dedup::{uuid.uuid4()}"
    pub = _publisher(worker_id)
    id1 = await pub.post_finding(subject, {"n": 1}, resolution_mechanism="human")
    id2 = await pub.post_finding(subject, {"n": 2}, resolution_mechanism="human")

    assert id1 == id2  # same standing row, not a duplicate
    async with get_session() as session:
        assert await _count_active(session, subject, "human") == 1
        r = await session.execute(
            text(
                "SELECT occurrence_count, payload->>'n', first_payload->>'n' "
                "FROM core.blackboard_entries WHERE id=:i"
            ),
            {"i": id1},
        )
        occ, latest, first = r.one()
    assert occ == 2
    assert latest == "2"  # latest evidence
    assert first == "1"  # original history retained


async def test_concurrent_posts_collapse_to_one_row(worker_id):
    subject = f"test.dedup.concurrent::{uuid.uuid4()}"
    pub = _publisher(worker_id)
    ids = await asyncio.gather(
        *[pub.post_finding(subject, {"n": i}, resolution_mechanism="reaudit") for i in range(5)]
    )
    assert len(set(ids)) == 1  # atomic: all collapse to one row, no race dup
    async with get_session() as session:
        assert await _count_active(session, subject, "reaudit") == 1
        r = await session.execute(
            text("SELECT occurrence_count FROM core.blackboard_entries WHERE id=:i"),
            {"i": ids[0]},
        )
    assert r.scalar_one() == 5


async def test_distinct_mechanism_is_distinct_identity(worker_id):
    subject = f"test.dedup.mech::{uuid.uuid4()}"
    pub = _publisher(worker_id)
    a = await pub.post_finding(subject, {}, resolution_mechanism="human")
    b = await pub.post_finding(subject, {}, resolution_mechanism="reaudit")

    assert a != b
    async with get_session() as session:
        assert await _count_active(session, subject, "human") == 1
        assert await _count_active(session, subject, "reaudit") == 1


async def test_last_seen_at_tracks_observation_not_mutation(worker_id):
    """last_seen_at moves only on a new observation (re-post), never on a generic
    mutation like a claim — that distinction is exactly why staleness keys on
    last_seen_at, not updated_at (which the touch trigger bumps on any change)."""
    subject = f"test.lastseen::{uuid.uuid4()}"
    pub = _publisher(worker_id)
    fid = await pub.post_finding(subject, {"n": 1}, resolution_mechanism="human")

    async with get_session() as session:
        r = await session.execute(
            text("SELECT last_seen_at, updated_at FROM core.blackboard_entries WHERE id=:i"),
            {"i": fid},
        )
        ls0, up0 = r.one()

    # Generic mutation (claim): touch trigger bumps updated_at; last_seen_at must NOT move.
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text("UPDATE core.blackboard_entries SET status='claimed' WHERE id=:i"),
                {"i": fid},
            )
    async with get_session() as session:
        r = await session.execute(
            text("SELECT last_seen_at, updated_at FROM core.blackboard_entries WHERE id=:i"),
            {"i": fid},
        )
        ls1, up1 = r.one()
    assert ls1 == ls0  # a claim did not refresh the observation timestamp
    assert up1 > up0  # generic mutation time did move

    # A real re-observation (re-post) DOES move last_seen_at (the 'claimed' row is
    # still non-terminal, so the upsert folds into it).
    again = await pub.post_finding(subject, {"n": 2}, resolution_mechanism="human")
    assert again == fid
    async with get_session() as session:
        r = await session.execute(
            text("SELECT last_seen_at FROM core.blackboard_entries WHERE id=:i"), {"i": fid}
        )
        ls2 = r.scalar_one()
    assert ls2 > ls1


async def test_resolver_closes_when_target_recovered(worker_id):
    async with get_session() as session:
        async with session.begin():
            target = await _insert_finding(
                session, worker_id, f"test.tgt::{uuid.uuid4()}", "open", "human", age_sec=10
            )
            alert = await _insert_finding(
                session, worker_id, f"blackboard.entry_stale::{target}", "open",
                "self_resolve", age_sec=10000, payload={"entry_id": str(target)},
            )
    await BlackboardService().resolve_stale_alerts_for_terminal_targets(stale_after_seconds=3600)
    async with get_session() as session:
        assert await _status(session, alert) == "resolved"


async def test_resolver_keeps_when_target_still_stale(worker_id):
    async with get_session() as session:
        async with session.begin():
            target = await _insert_finding(
                session, worker_id, f"test.tgt::{uuid.uuid4()}", "open", "human", age_sec=100000
            )
            alert = await _insert_finding(
                session, worker_id, f"blackboard.entry_stale::{target}", "open",
                "self_resolve", age_sec=10000, payload={"entry_id": str(target)},
            )
    await BlackboardService().resolve_stale_alerts_for_terminal_targets(stale_after_seconds=3600)
    async with get_session() as session:
        assert await _status(session, alert) == "open"


async def test_resolver_closes_when_target_terminal(worker_id):
    async with get_session() as session:
        async with session.begin():
            target = await _insert_finding(
                session, worker_id, f"test.tgt::{uuid.uuid4()}", "resolved", "human", age_sec=100000
            )
            alert = await _insert_finding(
                session, worker_id, f"blackboard.entry_stale::{target}", "open",
                "self_resolve", age_sec=10000, payload={"entry_id": str(target)},
            )
    await BlackboardService().resolve_stale_alerts_for_terminal_targets(stale_after_seconds=3600)
    async with get_session() as session:
        assert await _status(session, alert) == "resolved"


async def test_resolver_closes_when_target_missing(worker_id):
    missing = uuid.uuid4()
    async with get_session() as session:
        async with session.begin():
            alert = await _insert_finding(
                session, worker_id, f"blackboard.entry_stale::{missing}", "open",
                "self_resolve", age_sec=10000, payload={"entry_id": str(missing)},
            )
    await BlackboardService().resolve_stale_alerts_for_terminal_targets(stale_after_seconds=3600)
    async with get_session() as session:
        assert await _status(session, alert) == "resolved"
