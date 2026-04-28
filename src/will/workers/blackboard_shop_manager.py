# src/will/workers/blackboard_shop_manager.py
# ID: will.workers.blackboard_shop_manager
"""
BlackboardShopManager - Blackboard Health Supervisory Worker.

Responsibility: Detect Blackboard entries that have exceeded their
constitutional SLA and post a finding for each stale unclaimed or
unresolved entry.

Constitutional standing:
- Declaration:      .intent/workers/blackboard_shop_manager.yaml
- Class:            supervision
- Phase:            audit
- Permitted tools:  none — deterministic DB reads only
- Approval:         false — findings are observations only
- Schedule:         max_interval=120s, glide_off=12s (10% default)

SLA tiers (seconds):
- heartbeat entries:  600   (10 minutes)
- finding entries:    3600  (1 hour)
- report entries:     7200  (2 hours)
- proposal entries:   1800  (30 minutes)
- default:            3600  (1 hour)

Self-scheduling: BlackboardShopManager manages its own asyncio loop via
run_loop(). Sanctuary starts run_loop() once on bootstrap.

LAYER: will/workers — supervisory worker. Reads Blackboard only.
Writes findings to Blackboard. No LLM. No file writes.
"""

from __future__ import annotations

import asyncio
from typing import Any

from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)

_FINDING_SUBJECT = "blackboard.entry_stale"

# SLA per entry_type in seconds
_SLA: dict[str, int] = {
    "heartbeat": 600,
    "finding": 3600,
    "report": 7200,
    "proposal": 1800,
}
_SLA_DEFAULT = 3600


# ID: d4e5f6a7-c8d9-4e0f-1a2b-3c4d5e6f7a8b
class BlackboardShopManager(Worker):
    """
    Governance worker. Scans the Blackboard for entries that have
    exceeded their constitutional SLA and posts a finding for each.

    Uses deduplication — does not re-post a finding for an entry
    already flagged unless the previous finding is resolved.
    """

    declaration_name = "blackboard_shop_manager"

    def __init__(self) -> None:
        super().__init__()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 120)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * 0.10), 10)
        )

    # -------------------------------------------------------------------------
    # Self-scheduling entry point — called once by Sanctuary
    # -------------------------------------------------------------------------

    # ID: e5f6a7b8-d9e0-4f1a-2b3c-4d5e6f7a8b9c
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one audit cycle per
        max_interval seconds. Sanctuary calls this once on bootstrap.
        """
        logger.info(
            "BlackboardShopManager: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )
        await self._register()

        while True:
            try:
                await self.run()
            except Exception as exc:
                logger.error(
                    "BlackboardShopManager: cycle failed: %s", exc, exc_info=True
                )
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="blackboard_shop_manager.cycle_error",
                        payload={"error": str(exc)},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception(
                        "BlackboardShopManager: failed to post error report"
                    )

            await asyncio.sleep(self._max_interval)

    # -------------------------------------------------------------------------
    # Single audit cycle
    # -------------------------------------------------------------------------

    # ID: f6a7b8c9-e0f1-4a2b-3c4d-5e6f7a8b9c0d
    async def run(self) -> None:
        """
        Execute one Blackboard health cycle:
        1. Post heartbeat
        2. Fetch stale entries per SLA tier
        3. Post finding for each (deduplicated)
        4. Post completion report
        """
        await self.post_heartbeat()

        stale = await self._fetch_stale_entries()
        existing = await self._fetch_existing_findings()

        flagged = 0
        for entry in stale:
            entry_id = str(entry["id"])
            subject = f"{_FINDING_SUBJECT}::{entry_id}"

            if subject in existing:
                logger.debug(
                    "BlackboardShopManager: entry %s already flagged, skipping.",
                    entry_id,
                )
                continue

            await self.post_finding(
                subject=subject,
                payload={
                    "entry_id": entry_id,
                    "entry_type": entry["entry_type"],
                    "entry_subject": entry["subject"],
                    "worker_uuid": str(entry["worker_uuid"]),
                    "status": entry["status"],
                    "age_seconds": entry["age_seconds"],
                    "sla_seconds": entry["sla_seconds"],
                },
            )
            flagged += 1
            logger.warning(
                "BlackboardShopManager: entry %s (%s/%s) stale for %ds (sla=%ds)",
                entry_id,
                entry["entry_type"],
                entry["subject"],
                entry["age_seconds"],
                entry["sla_seconds"],
            )

        await self.post_report(
            subject="blackboard_shop_manager.run.complete",
            payload={
                "entries_checked": await self._count_active_entries(),
                "flagged": flagged,
            },
        )
        logger.info("BlackboardShopManager: cycle complete — flagged=%d", flagged)

    # -------------------------------------------------------------------------
    # DB reads — delegated to BlackboardService
    # -------------------------------------------------------------------------

    async def _fetch_stale_entries(self) -> list[dict[str, Any]]:
        """Return Blackboard entries that have exceeded their SLA tier."""
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.fetch_stale_entries()

    async def _fetch_existing_findings(self) -> set[str]:
        """
        Return subjects of open blackboard.entry_stale findings.

        Intentionally does NOT filter by worker_uuid. Deduplication must be
        by subject content, not by poster identity. This prevents different
        daemon generations from re-posting the same stale finding when their
        UUIDs differ across restarts.
        """
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.fetch_open_finding_subjects_by_prefix(f"{_FINDING_SUBJECT}::%")

    async def _count_active_entries(self) -> int:
        """Count total active Blackboard entries for the report."""
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.count_active_entries()
