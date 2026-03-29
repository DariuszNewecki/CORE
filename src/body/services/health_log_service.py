# src/body/services/health_log_service.py
"""
HealthLogService - Data-access layer for system state reads and
core.system_health_log writes.

Covers:
  - ObserverWorker._collect_state (all four count queries)
  - ObserverWorker._write_health_log
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)

# Must stay in sync with ObserverWorker._STALE_THRESHOLD_SECONDS.
_STALE_THRESHOLD_SECONDS = 3600


# ID: 1c26b39c-f6d2-4bee-a65c-bb24071ea25c
class HealthLogService:
    """
    Body layer service. Exposes system-state reads across
    core.blackboard_entries, core.worker_registry, and core.symbols,
    plus a write to core.system_health_log.
    All four read queries share a single session to match the
    original ObserverWorker._collect_state() semantics.
    """

    # ID: 1661aae5-c77e-4094-b057-4de80858bba9
    async def collect_system_state(
        self, stale_threshold_seconds: int = _STALE_THRESHOLD_SECONDS
    ) -> dict[str, Any]:
        """
        Run all four system-state count queries in one session and return
        a state dict with keys: open_findings, stale_entries,
        silent_workers, orphaned_symbols.

        Covers:
          - ObserverWorker._collect_state
          - ObserverWorker._count_open_findings
          - ObserverWorker._count_stale_entries
          - ObserverWorker._count_silent_workers
          - ObserverWorker._count_orphaned_symbols
        """
        from datetime import UTC, datetime

        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            r = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND status NOT IN ('resolved', 'abandoned')
                    """
                )
            )
            open_findings: int = r.scalar() or 0

            r = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.blackboard_entries
                    WHERE status NOT IN ('resolved', 'abandoned')
                      AND created_at < now() - make_interval(secs => :threshold)
                    """
                ),
                {"threshold": stale_threshold_seconds},
            )
            stale_entries: int = r.scalar() or 0

            r = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.worker_registry
                    WHERE status = 'active'
                      AND last_heartbeat < now() - interval '10 minutes'
                    """
                )
            )
            silent_workers: int = r.scalar() or 0

            r = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.symbols s1
                    WHERE s1.key IS NULL
                        AND s1.is_public = true
                        AND NOT EXISTS (
                        -- Check if any other symbol's 'calls' array contains this symbol's qualname
                        SELECT 1 FROM core.symbols s2
                        WHERE s2.calls @> to_jsonb(s1.qualname)
                        )
                    """
                )
            )
            orphaned_symbols: int = r.scalar() or 0

        return {
            "open_findings": open_findings,
            "stale_entries": stale_entries,
            "silent_workers": silent_workers,
            "orphaned_symbols": orphaned_symbols,
            "observed_at": datetime.now(UTC).isoformat(),
        }

    # ID: a32e06d3-3c7e-4724-b2b5-47f4b1eb1c92
    async def write_health_log(self, state: dict[str, Any]) -> None:
        """
        Append one row to core.system_health_log. Never updates existing rows.

        Covers:
          - ObserverWorker._write_health_log
        """
        from body.services.service_registry import ServiceRegistry

        async with ServiceRegistry.session() as session:
            async with session.begin():
                await session.execute(
                    text(
                        """
                        INSERT INTO core.system_health_log
                            (open_findings, stale_entries, silent_workers,
                             orphaned_symbols, payload)
                        VALUES
                            (:open_findings, :stale_entries, :silent_workers,
                             :orphaned_symbols, cast(:payload as jsonb))
                        """
                    ),
                    {
                        "open_findings": state["open_findings"],
                        "stale_entries": state["stale_entries"],
                        "silent_workers": state["silent_workers"],
                        "orphaned_symbols": state["orphaned_symbols"],
                        "payload": "{}",
                    },
                )
