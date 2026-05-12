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

from body.services.worker_registry_service import WorkerRegistryService
from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.workers.schedule import load_worker_schedule_state


logger = getLogger(__name__)

_CFG = load_operational_config().health_log


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
        self, stale_threshold_seconds: int = _CFG.stale_threshold_seconds
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
                      AND status NOT IN (
                          'resolved',
                          'abandoned',
                          'suppressed',
                          'dry_run_complete',
                          'deferred_to_proposal',
                          'indeterminate'
                      )
                    """
                )
            )
            open_findings: int = r.scalar() or 0

            r = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.blackboard_entries
                    WHERE status NOT IN (
                          'resolved',
                          'abandoned',
                          'suppressed',
                          'dry_run_complete',
                          'deferred_to_proposal',
                          'indeterminate'
                      )
                      AND created_at < now() - make_interval(secs => :threshold)
                    """
                ),
                {"threshold": stale_threshold_seconds},
            )
            stale_entries: int = r.scalar() or 0

            # silent_workers per ADR-041 D2/D3: per-worker thresholds from
            # the shared schedule loader, plus orphan-skip. Same canonical
            # rule WorkerShopManager and the runtime dashboard apply.
            schedule_state = load_worker_schedule_state()
            registry_svc = WorkerRegistryService()
            silent_rows = await registry_svc.fetch_stale_workers_with_schedules(
                thresholds=schedule_state.thresholds,
                active_uuids=schedule_state.active_uuids,
                fallback_sec=schedule_state.fallback_sec,
            )
            silent_workers: int = len(silent_rows)

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
