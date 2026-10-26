# src/shared/workers/registry_sql.py
"""
Worker lifecycle SQL — the worker_registry and claim-release statements.

Split out of shared/workers/base.py (modularity.class_too_large, #1280):
the Worker lifecycle methods (_register, _renew_registry_heartbeat,
_release_held_claims) stay on Worker and delegate their statements here.

LAYER: shared/workers — DB access is legitimate here: blackboard and
worker_registry ARE the infrastructure.
"""

from __future__ import annotations

import uuid

from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session


# ID: 96710ad5-6f34-4ec3-982b-1f606e00cf5c
async def upsert_worker_registration(
    *,
    worker_uuid: uuid.UUID,
    worker_name: str,
    worker_class: str,
    phase: str,
    declaration_name: str,
) -> None:
    """Insert or refresh this worker's row in core.worker_registry."""
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    insert into core.worker_registry
                        (worker_uuid, worker_name, worker_class, phase,
                         declaration_name, last_heartbeat)
                    values
                        (:worker_uuid, :worker_name, :worker_class, :phase,
                         :declaration_name, now())
                    on conflict (worker_uuid) do update set
                        worker_name = excluded.worker_name,
                        worker_class = excluded.worker_class,
                        phase = excluded.phase,
                        declaration_name = excluded.declaration_name,
                        last_heartbeat = now()
"""
                ),
                {
                    "worker_uuid": worker_uuid,
                    "worker_name": worker_name,
                    "worker_class": worker_class,
                    "phase": phase,
                    "declaration_name": declaration_name,
                },
            )


# ID: 24115833-ab76-4a5d-a298-e4de3200a8b1
async def touch_registry_heartbeat(worker_uuid: uuid.UUID) -> None:
    """Set worker_registry.last_heartbeat = now() for this worker (ADR-104 D8)."""
    async with get_session() as session:
        async with session.begin():
            await session.execute(
                text(
                    """
                    update core.worker_registry
                       set last_heartbeat = now()
                     where worker_uuid = :worker_uuid
                    """
                ),
                {"worker_uuid": worker_uuid},
            )


# ID: 2fcf48d2-e534-4fee-a621-d22fe8a25422
async def release_claims_held_by(worker_uuid: uuid.UUID) -> int:
    """Reopen every blackboard entry this worker holds as 'claimed'.

    Single-statement UPDATE filtered by claimed_by + status='claimed' —
    idempotent. Returns the number of rows released.
    """
    async with get_session() as session:
        async with session.begin():
            result = await session.execute(
                text(
                    """
                    update core.blackboard_entries
                       set status = 'open',
                           claimed_by = null,
                           updated_at = now()
                     where claimed_by = :worker_uuid
                       and status = 'claimed'
                    """
                ),
                {"worker_uuid": worker_uuid},
            )
            return getattr(result, "rowcount", 0)
