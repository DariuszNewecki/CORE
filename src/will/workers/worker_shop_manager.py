# src/will/workers/worker_shop_manager.py
"""
WorkerShopManager - Worker Liveness Supervisory Worker.

Responsibility: Detect workers that have missed their declared heartbeat
schedule and post a finding to the Blackboard for each silent or abandoned
worker.

Constitutional standing:
- Declaration:      .intent/workers/worker_shop_manager.yaml
- Class:            supervision
- Phase:            audit
- Permitted tools:  none — deterministic DB reads only
- Approval:         false — findings are observations only
- Schedule:         max_interval=120s, glide_off=12s (10% default)

Self-scheduling: WorkerShopManager manages its own asyncio loop via run_loop().
Sanctuary starts run_loop() once on bootstrap.

LAYER: will/workers — supervisory worker. Reads worker_registry, reads
.intent/workers/ declarations for scheduled workers. Writes to Blackboard
only. No LLM. No file writes.
"""

from __future__ import annotations

import asyncio
import re
import time
from typing import Any

from shared.infrastructure.intent.operational_config import load_operational_config
from shared.logger import getLogger
from shared.workers.base import Worker
from shared.workers.schedule import (
    WorkerScheduleState,
    load_worker_schedule_state,
)


logger = getLogger(__name__)

_FINDING_SUBJECT = "worker.silent"

_CFG = load_operational_config().workers.worker_shop

# Strip non-ASCII characters that PostgreSQL SQL_ASCII encoding cannot store.
# Worker names from .intent/workers/ YAML titles may contain Unicode dashes or
# other decorative characters that cause UntranslatableCharacterError on insert.
_NON_ASCII_RE = re.compile(r"[^\x09\x0A\x0D\x20-\x7E]")


def _sanitize(value: str) -> str:
    """Replace non-ASCII characters with '?' for SQL_ASCII database safety."""
    if not isinstance(value, str):
        return str(value)
    return _NON_ASCII_RE.sub("?", value)


# ID: c3e4f5a6-b7c8-4d9e-0f1a-2b3c4d5e6f7a
class WorkerShopManager(Worker):
    """
    Governance worker. Reads worker_registry, computes per-worker liveness
    thresholds from .intent/ declarations, and posts a finding for each
    worker that has exceeded max_interval + glide_off since last heartbeat.

    Uses deduplication — does not re-post a finding for a worker already
    flagged as silent unless the previous finding is resolved.
    """

    declaration_name = "worker_shop_manager"

    def __init__(self) -> None:
        super().__init__()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 120)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * _CFG.glide_off_multiplier), 10)
        )
        # Per-worker schedule state loaded once per cycle from .intent/workers/.
        # Sourced via the shared loader (ADR-041 D4) so the dashboard and
        # health_log_service apply the same per-worker thresholds and the same
        # orphan-skip rule as this supervisor.
        self._schedule_state: WorkerScheduleState = WorkerScheduleState(
            thresholds={},
            active_uuids=frozenset(),
            fallback_sec=_CFG.fallback_threshold_sec,
        )

    # -------------------------------------------------------------------------
    # Self-scheduling entry point — called once by Sanctuary
    # -------------------------------------------------------------------------

    # ID: d4f5a6b7-c8d9-4e0f-1a2b-3c4d5e6f7a8b
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one audit cycle per
        max_interval seconds. Sanctuary calls this once on bootstrap.
        """
        logger.info(
            "WorkerShopManager: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )
        await self._register()

        while True:
            cycle_start = time.monotonic()
            try:
                await self.run()
            except Exception as exc:
                logger.error("WorkerShopManager: cycle failed: %s", exc, exc_info=True)
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="worker_shop_manager.cycle_error",
                        payload={"error": _sanitize(str(exc))},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception("WorkerShopManager: failed to post error report")

            elapsed = time.monotonic() - cycle_start
            await asyncio.sleep(max(self._max_interval - elapsed, 0))

    # -------------------------------------------------------------------------
    # Single audit cycle
    # -------------------------------------------------------------------------

    # ID: e5a6b7c8-d9e0-4f1a-2b3c-4d5e6f7a8b9c
    async def run(self) -> None:
        """
        Execute one liveness audit cycle:
        1. Post heartbeat
        2. Load per-worker schedules from .intent/
        3. Fetch registered workers from DB
        4. For each worker exceeding threshold: post finding (deduplicated)
        5. Resolve open findings whose worker has resumed heartbeating
        6. Post completion report
        """
        from body.services.service_registry import service_registry

        await self.post_heartbeat()

        self._schedule_state = load_worker_schedule_state()
        workers = await self._fetch_registered_workers(service_registry)
        existing = await self._fetch_existing_findings(service_registry)

        flagged = 0
        flagged_subjects: set[str] = set()
        for worker in workers:
            # Sanitize worker_name — registry may contain non-ASCII characters
            # from YAML titles (e.g. em dashes). SQL_ASCII encoding rejects them.
            worker_name = _sanitize(worker["worker_name"])
            worker_uuid = str(worker["worker_uuid"])
            seconds_silent = worker["seconds_silent"]

            if worker_uuid not in self._schedule_state.active_uuids:
                logger.debug(
                    "WorkerShopManager: skipping orphan registry row "
                    "%s (%s) — UUID not declared in any active worker YAML",
                    worker_uuid,
                    worker_name,
                )
                continue

            threshold = self._schedule_state.thresholds.get(
                worker_uuid, _CFG.fallback_threshold_sec
            )

            if seconds_silent > threshold:
                subject = f"{_FINDING_SUBJECT}::{worker_uuid}"
                flagged_subjects.add(subject)
                if subject in existing:
                    logger.debug(
                        "WorkerShopManager: %s already flagged, skipping.", worker_name
                    )
                    continue

                await self.post_observation(
                    subject=subject,
                    payload={
                        "worker_name": worker_name,
                        "worker_uuid": worker_uuid,
                        "seconds_silent": seconds_silent,
                        "threshold": threshold,
                    },
                    status="abandoned",
                )
                flagged += 1
                logger.warning(
                    "WorkerShopManager: %s silent for %ds (threshold=%ds)",
                    worker_name,
                    seconds_silent,
                    threshold,
                )

        # Resolution pass — any open worker.silent finding whose subject is
        # no longer over threshold means the worker has resumed heartbeating.
        svc = await service_registry.get_blackboard_service()
        resolved = 0
        for subject, entry_id in existing.items():
            if subject not in flagged_subjects:
                await svc.resolve_entries([entry_id])
                resolved += 1
                logger.info(
                    "WorkerShopManager: %s recovered — resolving open finding",
                    subject,
                )

        await self.post_report(
            subject="worker_shop_manager.run.complete",
            payload={
                "workers_checked": len(workers),
                "flagged": flagged,
                "resolved": resolved,
            },
        )
        logger.info(
            "WorkerShopManager: cycle complete — checked=%d flagged=%d resolved=%d",
            len(workers),
            flagged,
            resolved,
        )

    # -------------------------------------------------------------------------
    # DB reads
    # -------------------------------------------------------------------------

    async def _fetch_registered_workers(self, registry: Any) -> list[dict[str, Any]]:
        """Return all active workers with seconds since last heartbeat."""
        svc = await registry.get_worker_registry_service()
        return await svc.fetch_registered_workers()

    async def _fetch_existing_findings(self, registry: Any) -> dict[str, str]:
        """
        Return mapping of subject → entry_id for open worker.silent findings.

        The entry_id is needed so the resolution pass in run() can call
        resolve_entries() on findings whose worker has recovered.
        """
        svc = await registry.get_blackboard_service()
        rows = await svc.fetch_open_findings(prefix=f"{_FINDING_SUBJECT}::%", limit=200)
        return {row["subject"]: row["id"] for row in rows}
