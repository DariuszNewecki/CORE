# src/will/workers/observer_worker.py
# ID: will.workers.observer_worker
"""
ObserverWorker - System State Sensing Worker.

Responsibility: Observe system state across all constitutional domains and post
a structured situation report to the Blackboard and system_health_log.

Constitutional standing:
- Declaration:      .intent/workers/observer_worker.yaml
- Class:            sensing
- Phase:            audit
- Permitted tools:  none — deterministic DB reads only
- Approval:         false — reports are observations only
- Schedule:         max_interval=300s, glide_off=30s (10% default)

Self-scheduling: ObserverWorker manages its own asyncio loop via run_loop().
Sanctuary starts run_loop() once on bootstrap. run() is a single observation
cycle — it never loops internally.

LAYER: will/workers — sensing worker. Reads DB, writes Blackboard and
system_health_log. No LLM. No file writes. No direct worker communication.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

# Blackboard subject for situation reports
_REPORT_SUBJECT = "observer.situation_report"

# Seconds an open blackboard entry must be open before counted as stale
_STALE_THRESHOLD_SECONDS = 3600


# ID: a7f3c2e1-b4d5-4e6f-8a9b-0c1d2e3f4a5b
class ObserverWorker(Worker):
    """
    Sensing worker. Reads system state from the DB and posts a structured
    situation report to the Blackboard and core.system_health_log.

    No LLM. No writes to src/ or .intent/. Pure perception.
    """

    declaration_name = "observer_worker"

    def __init__(self) -> None:
        super().__init__()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 300)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * 0.10), 10)
        )

    # -------------------------------------------------------------------------
    # Self-scheduling entry point — called once by Sanctuary
    # -------------------------------------------------------------------------

    # ID: b8c4d3e2-a5f6-4e7f-9b0c-1d2e3f4a5b6c
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one observation cycle per
        max_interval seconds. Sanctuary calls this once on bootstrap.

        Never raises — exceptions are caught, logged, and posted to the
        Blackboard. The loop continues regardless of individual cycle failures.
        """
        logger.info(
            "ObserverWorker: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )
        await self._register()

        while True:
            try:
                await self.run()
            except Exception as exc:
                logger.error("ObserverWorker: cycle failed: %s", exc, exc_info=True)
                # Post error to Blackboard so Orchestrator can see it
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="observer.cycle_error",
                        payload={"error": str(exc)},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception("ObserverWorker: failed to post error report")

            await asyncio.sleep(self._max_interval)

    # -------------------------------------------------------------------------
    # Single observation cycle
    # -------------------------------------------------------------------------

    # ID: c9d5e4f3-b6a7-4f8e-0c1d-2e3f4a5b6c7d
    async def run(self) -> None:
        """
        Execute one observation cycle:
        1. Post heartbeat
        2. Collect system state counts
        3. Write to system_health_log
        4. Post situation report to Blackboard
        """
        await self.post_heartbeat()

        state = await self._collect_state()

        await self._write_health_log(state)

        await self.post_report(
            subject=_REPORT_SUBJECT,
            payload=state,
        )

        logger.info(
            "ObserverWorker: cycle complete — open_findings=%d stale=%d "
            "silent_workers=%d orphaned_symbols=%d",
            state["open_findings"],
            state["stale_entries"],
            state["silent_workers"],
            state["orphaned_symbols"],
        )

    # -------------------------------------------------------------------------
    # State collection — pure DB reads
    # -------------------------------------------------------------------------

    # ID: d0e6f5a4-c7b8-4a9f-1d2e-3f4a5b6c7d8e
    async def _collect_state(self) -> dict[str, Any]:
        """Read system state counts from the DB. No LLM. No side effects."""
        async with get_session() as session:
            open_findings = await self._count_open_findings(session)
            stale_entries = await self._count_stale_entries(session)
            silent_workers = await self._count_silent_workers(session)
            orphaned_symbols = await self._count_orphaned_symbols(session)

        return {
            "open_findings": open_findings,
            "stale_entries": stale_entries,
            "silent_workers": silent_workers,
            "orphaned_symbols": orphaned_symbols,
            "observed_at": datetime.now(UTC).isoformat(),
        }

    async def _count_open_findings(self, session: Any) -> int:
        result = await session.execute(
            text(
                """
                SELECT COUNT(*) FROM core.blackboard_entries
                WHERE entry_type = 'finding'
                  AND status NOT IN ('resolved', 'abandoned')
                """
            )
        )
        return result.scalar() or 0

    async def _count_stale_entries(self, session: Any) -> int:
        result = await session.execute(
            text(
                """
                SELECT COUNT(*) FROM core.blackboard_entries
                WHERE status NOT IN ('resolved', 'abandoned')
                  AND created_at < now() - make_interval(secs => :threshold)
                """
            ),
            {"threshold": _STALE_THRESHOLD_SECONDS},
        )
        return result.scalar() or 0

    async def _count_silent_workers(self, session: Any) -> int:
        result = await session.execute(
            text(
                """
                SELECT COUNT(*) FROM core.worker_registry
                WHERE status = 'active'
                  AND last_heartbeat < now() - interval '10 minutes'
                """
            )
        )
        return result.scalar() or 0

    async def _count_orphaned_symbols(self, session: Any) -> int:
        result = await session.execute(
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
        return result.scalar() or 0

    # -------------------------------------------------------------------------
    # Health log write
    # -------------------------------------------------------------------------

    # ID: e1f7a6b5-d8c9-4b0f-2e3f-4a5b6c7d8e9f
    async def _write_health_log(self, state: dict[str, Any]) -> None:
        """Append one row to core.system_health_log. Never updates existing rows."""
        async with get_session() as session:
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
