# tests/will/workers/test_proposal_pipeline_shop_manager_stuck_deferred_terminal_db.py
"""Integration: a finding stranded in ``deferred_to_proposal`` on a proposal
that already ``failed`` is found by ``fetch_stuck_deferred_terminal`` and
revived to ``awaiting_reaudit`` by the shop manager's reconcile pass — the
exact shape of the six live ``style.formatter_required`` findings stranded
since 2026-07-26 (G4 P2 pre-condition).

Drives the real supervision query and the real reconcile method against the
test DB; only the Worker surface (heartbeat/finding/report/observation
posts) is stubbed, since posting needs the daemon's worker identity.
Synthetic UUIDs + self-cleanup, same pattern as test_remediation_attempt_cap.py.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from body.services.service_registry import service_registry
from shared.infrastructure.database.session_manager import get_session
from will.workers.proposal_pipeline_shop_manager import ProposalPipelineShopManager


pytestmark = [pytest.mark.integration]

_SYNTH_NAME = "test.g4p2.stuck_deferred_terminal"


@pytest.fixture(autouse=True)
def _prime_service_registry() -> None:
    service_registry.prime(get_session)


def _make_worker() -> ProposalPipelineShopManager:
    w = object.__new__(ProposalPipelineShopManager)
    w._declaration = {}
    w._max_interval = 300
    w._worker_uuid = uuid.uuid4()
    w.post_heartbeat = AsyncMock()  # type: ignore[method-assign]
    w.post_finding = AsyncMock()  # type: ignore[method-assign]
    w.post_report = AsyncMock()  # type: ignore[method-assign]
    w.post_observation = AsyncMock()  # type: ignore[method-assign]
    return w


async def _seed(
    db_session: AsyncSession, *, worker_uuid: uuid.UUID, proposal_id: str, entry_id: str
) -> None:
    long_ago = datetime.now(UTC) - timedelta(days=2)
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
    await db_session.execute(
        text(
            """
            insert into core.autonomous_proposals
                (proposal_id, goal, status, actions, scope, constitutional_constraints,
                 approval_required, created_at, execution_started_at,
                 execution_completed_at, execution_results, failure_reason)
            values
                (:pid, 'stuck-deferred-terminal seed', 'failed',
                 cast(:actions as jsonb), cast('{"files": []}' as jsonb),
                 cast(:cc as jsonb), false, :t, :t, :t, cast('{}' as jsonb),
                 'seeded failure whose revival never ran')
            """
        ),
        {
            "pid": proposal_id,
            "actions": json.dumps(
                [{"action_id": "fix.format", "parameters": {"write": True}, "order": 0}]
            ),
            "cc": json.dumps({"finding_ids": [entry_id]}),
            "t": long_ago,
        },
    )
    await db_session.execute(
        text(
            """
            insert into core.blackboard_entries
                (id, worker_uuid, entry_type, phase, status, subject, payload,
                 resolution_mechanism, claimed_by, claimed_at, resolved_at,
                 created_at, updated_at)
            values
                (cast(:id as uuid), :worker_uuid, 'finding', 'audit',
                 'deferred_to_proposal', :subject, cast(:payload as jsonb),
                 'reaudit', :worker_uuid, :t, :t, :t, :t)
            """
        ),
        {
            "id": entry_id,
            "worker_uuid": worker_uuid,
            "subject": f"python::style.formatter_required::src/t_g4p2_{entry_id[:8]}.py",
            "payload": json.dumps(
                {
                    "file_path": f"src/t_g4p2_{entry_id[:8]}.py",
                    "rule": "style.formatter_required",
                    "proposal_id": proposal_id,
                }
            ),
            "t": long_ago,
        },
    )
    await db_session.commit()


async def _cleanup(
    db_session: AsyncSession, *, worker_uuid: uuid.UUID, proposal_id: str, entry_id: str
) -> None:
    await db_session.rollback()
    await db_session.execute(
        text("delete from core.blackboard_entries where id = cast(:id as uuid)"),
        {"id": entry_id},
    )
    await db_session.execute(
        text("delete from core.autonomous_proposals where proposal_id = :pid"),
        {"pid": proposal_id},
    )
    await db_session.execute(
        text(
            "delete from core.worker_registry where worker_uuid = :u and worker_name = :n"
        ),
        {"u": worker_uuid, "n": _SYNTH_NAME},
    )
    await db_session.commit()


# ID: 77aafb74-48f3-4b44-83e7-d11ea325b956
async def test_finding_stranded_on_failed_proposal_is_revived(
    db_session: AsyncSession,
) -> None:
    emitter = uuid.uuid4()
    proposal_id = f"test-g4p2-{uuid.uuid4().hex[:8]}"
    entry_id = str(uuid.uuid4())
    await _seed(
        db_session, worker_uuid=emitter, proposal_id=proposal_id, entry_id=entry_id
    )
    try:
        svc = await service_registry.get_proposal_supervision_service()
        rows = await svc.fetch_stuck_deferred_terminal(sla_sec=120, limit=500)
        mine = [r for r in rows if r["proposal_id"] == proposal_id]
        assert len(mine) == 1
        assert mine[0]["proposal_status"] == "failed"
        assert mine[0]["finding_ids"] == [entry_id]
        assert mine[0]["nothing_to_commit"] is False
        assert mine[0]["seconds_stuck"] > 120

        worker = _make_worker()
        assert await worker._reconcile_stuck_deferred_terminal(mine[0]) is True  # type: ignore[attr-defined]

        db_session.expire_all()
        row = (
            await db_session.execute(
                text(
                    """
                    select status, claimed_by,
                           (payload->>'remediation_attempt_count')::int as attempts
                      from core.blackboard_entries where id = cast(:id as uuid)
                    """
                ),
                {"id": entry_id},
            )
        ).one()
        assert row.status == "awaiting_reaudit"
        assert row.claimed_by is None
        assert row.attempts == 1  # ADR-104 D9 counter moved: this was an attempt

        # The row is gone from the query — the pass is its own resolver.
        rows = await svc.fetch_stuck_deferred_terminal(sla_sec=120, limit=500)
        assert not [r for r in rows if r["proposal_id"] == proposal_id]
        # The revival was reported through the Worker.
        assert worker.post_report.await_count >= 1
    finally:
        await _cleanup(
            db_session, worker_uuid=emitter, proposal_id=proposal_id, entry_id=entry_id
        )
