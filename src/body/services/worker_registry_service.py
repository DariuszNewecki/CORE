# src/body/services/worker_registry_service.py
"""
WorkerRegistryService - Data-access layer for core.worker_registry.

Covers:
  - WorkerShopManager._fetch_registered_workers

Note: WorkerShopManager._fetch_existing_findings queries core.blackboard_entries
and is already covered by BlackboardService.fetch_open_finding_subjects_by_prefix().
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: ae3a0db7-f91b-4844-b41b-cb0ecb01fb79
class WorkerRegistryService:
    """
    Body layer service. Exposes named methods for core.worker_registry
    queries used by WorkerShopManager and runtime health readers.

    Per ADR-020, worker liveness is derived from last_heartbeat against
    a threshold; there is no status column. Callers needing a liveness
    view use fetch_alive_workers / fetch_stale_workers.
    """

    # ID: 8ac6e97e-9597-49af-a285-de8da66bda4b
    async def fetch_registered_workers(self) -> list[dict[str, Any]]:
        """
        Return all registered workers with seconds since last heartbeat,
        ordered by silence duration descending. No liveness filter is
        applied here — callers wanting alive-only or stale-only sets
        use fetch_alive_workers / fetch_stale_workers.

        Covers:
          - WorkerShopManager._fetch_registered_workers
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        worker_uuid,
                        worker_name,
                        worker_class,
                        phase,
                        last_heartbeat,
                        EXTRACT(EPOCH FROM (now() - last_heartbeat))::int
                            AS seconds_silent
                    FROM core.worker_registry
                    ORDER BY seconds_silent DESC
                    """
                )
            )
            return [
                {
                    "worker_uuid": row[0],
                    "worker_name": row[1],
                    "worker_class": row[2],
                    "phase": row[3],
                    "last_heartbeat": row[4],
                    "seconds_silent": row[5] or 0,
                }
                for row in result.fetchall()
            ]

    # ID: 7d8e9f0a-1b2c-4d5e-6f7a-8b9c0d1e2f3a
    async def fetch_alive_workers(self, threshold_sec: int) -> list[dict[str, Any]]:
        """
        Return workers whose last_heartbeat is within the threshold.

        'Alive' means heartbeat freshness is below threshold_sec seconds.
        Per ADR-020, this is the canonical liveness derivation.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        worker_uuid,
                        worker_name,
                        worker_class,
                        phase,
                        last_heartbeat,
                        EXTRACT(EPOCH FROM (now() - last_heartbeat))::int
                            AS seconds_silent
                    FROM core.worker_registry
                    WHERE last_heartbeat > now() - make_interval(secs => :threshold)
                    ORDER BY last_heartbeat DESC
                    """
                ),
                {"threshold": threshold_sec},
            )
            return [
                {
                    "worker_uuid": row[0],
                    "worker_name": row[1],
                    "worker_class": row[2],
                    "phase": row[3],
                    "last_heartbeat": row[4],
                    "seconds_silent": row[5] or 0,
                }
                for row in result.fetchall()
            ]

    # ID: 8e9f0a1b-2c3d-4e5f-6a7b-8c9d0e1f2a3b
    async def fetch_stale_workers(self, threshold_sec: int) -> list[dict[str, Any]]:
        """
        Return workers whose last_heartbeat exceeds the threshold.

        Per ADR-020, these are the workers a supervisor or dashboard
        should treat as not alive. The supervisor (WorkerShopManager)
        continues to use per-worker SLAs from .intent/workers/*.yaml;
        this method is for table-wide queries with a single threshold.
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        worker_uuid,
                        worker_name,
                        worker_class,
                        phase,
                        last_heartbeat,
                        EXTRACT(EPOCH FROM (now() - last_heartbeat))::int
                            AS seconds_silent
                    FROM core.worker_registry
                    WHERE last_heartbeat <= now() - make_interval(secs => :threshold)
                    ORDER BY seconds_silent DESC
                    """
                ),
                {"threshold": threshold_sec},
            )
            return [
                {
                    "worker_uuid": row[0],
                    "worker_name": row[1],
                    "worker_class": row[2],
                    "phase": row[3],
                    "last_heartbeat": row[4],
                    "seconds_silent": row[5] or 0,
                }
                for row in result.fetchall()
            ]
