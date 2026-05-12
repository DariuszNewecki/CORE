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

    # ID: 9a3c1e5d-7b8f-4a0c-9d2e-5f6a7b8c9d0e
    async def fetch_stale_workers_with_schedules(
        self,
        thresholds: dict[str, int],
        active_uuids: frozenset[str] | set[str],
        fallback_sec: int,
    ) -> list[dict[str, Any]]:
        """
        Return workers considered stale under per-worker rules (ADR-041 D2).

        For each registered worker:
          - Skip if its worker_uuid is not in *active_uuids* (orphan-skip,
            ADR-041 D3). Orphans never produce a "stale" verdict.
          - Otherwise compare seconds_silent against
            ``thresholds.get(worker_uuid, fallback_sec)``. Return the row
            if seconds_silent exceeds the threshold.

        Callers obtain *thresholds* and *active_uuids* from
        ``shared.workers.schedule.load_worker_schedule_state()`` so the
        producer (WorkerShopManager) and downstream readers (dashboard,
        health_log_service) apply identical liveness semantics.

        The variable-threshold-per-row requirement does not map cleanly
        to a single SQL parameter, so filtering is applied in Python
        after fetching. Row count is small (one row per registered
        worker, currently ~20), making post-query filtering appropriate.
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
            stale: list[dict[str, Any]] = []
            for row in result.fetchall():
                worker_uuid_str = str(row[0])
                if worker_uuid_str not in active_uuids:
                    continue
                seconds_silent = row[5] or 0
                threshold = thresholds.get(worker_uuid_str, fallback_sec)
                if seconds_silent > threshold:
                    stale.append(
                        {
                            "worker_uuid": row[0],
                            "worker_name": row[1],
                            "worker_class": row[2],
                            "phase": row[3],
                            "last_heartbeat": row[4],
                            "seconds_silent": seconds_silent,
                            "threshold": threshold,
                        }
                    )
            return stale

    # ID: 8e9f0a1b-2c3d-4e5f-6a7b-8c9d0e1f2a3b
    async def fetch_stale_workers(self, threshold_sec: int) -> list[dict[str, Any]]:
        """
        Return workers whose last_heartbeat exceeds a single global threshold.

        DEPRECATED per ADR-041 — does not honour per-worker schedules and
        does not skip orphan rows (registry rows whose UUID is not
        declared by any active .intent/workers/*.yaml). New callers should
        use fetch_stale_workers_with_schedules. Retained for one commit
        cycle while migration completes.
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
