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
    queries used by WorkerShopManager.
    """

    # ID: 8ac6e97e-9597-49af-a285-de8da66bda4b
    async def fetch_registered_workers(self) -> list[dict[str, Any]]:
        """
        Return all non-abandoned workers with seconds since last heartbeat,
        ordered by silence duration descending.

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
                        status,
                        EXTRACT(EPOCH FROM (now() - last_heartbeat))::int
                            AS seconds_silent
                    FROM core.worker_registry
                    WHERE status != 'abandoned'
                    ORDER BY seconds_silent DESC
                    """
                )
            )
            return [
                {
                    "worker_uuid": row[0],
                    "worker_name": row[1],
                    "status": row[2],
                    "seconds_silent": row[3] or 0,
                }
                for row in result.fetchall()
            ]
