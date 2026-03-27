# src/will/workers/blackboard_auditor.py
# ID: will.workers.blackboard_auditor
"""
BlackboardAuditor - Blackboard Health Governance Worker.

Responsibility: Detect Blackboard entries that have exceeded their
constitutional SLA and post a finding for each stale unclaimed or
unresolved entry.

Constitutional standing:
- Declaration:      .intent/workers/blackboard_auditor.yaml
- Class:            governance
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

Self-scheduling: BlackboardAuditor manages its own asyncio loop via
run_loop(). Sanctuary starts run_loop() once on bootstrap.

LAYER: will/workers — governance worker. Reads Blackboard only.
Writes findings to Blackboard. No LLM. No file writes.
"""

from __future__ import annotations

import asyncio
from typing import Any

from sqlalchemy import text

from shared.infrastructure.database.session_manager import get_session
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
class BlackboardAuditor(Worker):
    """
    Governance worker. Scans the Blackboard for entries that have
    exceeded their constitutional SLA and posts a finding for each.

    Uses deduplication — does not re-post a finding for an entry
    already flagged unless the previous finding is resolved.
    """

    declaration_name = "blackboard_auditor"

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
            "BlackboardAuditor: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )
        await self._register()

        while True:
            try:
                await self.run()
            except Exception as exc:
                logger.error("BlackboardAuditor: cycle failed: %s", exc, exc_info=True)
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="blackboard_auditor.cycle_error",
                        payload={"error": str(exc)},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception("BlackboardAuditor: failed to post error report")

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
                    "BlackboardAuditor: entry %s already flagged, skipping.",
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
                "BlackboardAuditor: entry %s (%s/%s) stale for %ds (sla=%ds)",
                entry_id,
                entry["entry_type"],
                entry["subject"],
                entry["age_seconds"],
                entry["sla_seconds"],
            )

        await self.post_report(
            subject="blackboard_auditor.run.complete",
            payload={
                "entries_checked": await self._count_active_entries(),
                "flagged": flagged,
            },
        )
        logger.info("BlackboardAuditor: cycle complete — flagged=%d", flagged)

    # -------------------------------------------------------------------------
    # DB reads
    # -------------------------------------------------------------------------

    async def _fetch_stale_entries(self) -> list[dict[str, Any]]:
        """
        Return Blackboard entries that have exceeded their SLA tier.
        """
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT
                        id,
                        entry_type,
                        subject,
                        worker_uuid,
                        status,
                        EXTRACT(EPOCH FROM (now() - created_at))::int AS age_seconds,
                        CASE entry_type
                            WHEN 'heartbeat' THEN CAST(:sla_heartbeat AS INT)
                            WHEN 'finding'   THEN CAST(:sla_finding AS INT)
                            WHEN 'report'    THEN CAST(:sla_report AS INT)
                            WHEN 'proposal'  THEN CAST(:sla_proposal AS INT)
                            ELSE CAST(:sla_default AS INT)
                        END AS sla_seconds
                    FROM core.blackboard_entries
                    WHERE status NOT IN ('resolved', 'abandoned')
                      AND subject NOT LIKE 'blackboard.entry_stale::%'
                      AND subject NOT LIKE 'worker.silent::%'
                      AND EXTRACT(EPOCH FROM (now() - created_at)) >
                        CASE entry_type
                            WHEN 'heartbeat' THEN CAST(:sla_heartbeat AS INT)
                            WHEN 'finding'   THEN CAST(:sla_finding AS INT)
                            WHEN 'report'    THEN CAST(:sla_report AS INT)
                            WHEN 'proposal'  THEN CAST(:sla_proposal AS INT)
                            ELSE CAST(:sla_default AS INT)
                        END
                    ORDER BY age_seconds DESC
                    """
                ),
                {
                    "sla_heartbeat": _SLA["heartbeat"],
                    "sla_finding": _SLA["finding"],
                    "sla_report": _SLA["report"],
                    "sla_proposal": _SLA["proposal"],
                    "sla_default": _SLA_DEFAULT,
                },
            )
            return [
                {
                    "id": row[0],
                    "entry_type": row[1],
                    "subject": row[2],
                    "worker_uuid": row[3],
                    "status": row[4],
                    "age_seconds": row[5] or 0,
                    "sla_seconds": row[6],
                }
                for row in result.fetchall()
            ]

    async def _fetch_existing_findings(self) -> set[str]:
        """
        Return subjects of open blackboard.entry_stale findings.

        Intentionally does NOT filter by worker_uuid. Deduplication must be
        by subject content, not by poster identity. This prevents different
        daemon generations from re-posting the same stale finding when their
        UUIDs differ across restarts.
        """
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT subject FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND subject LIKE :prefix
                      AND status NOT IN ('resolved', 'abandoned')
                    """
                ),
                {"prefix": f"{_FINDING_SUBJECT}::%"},
            )
            return {row[0] for row in result.fetchall()}

    async def _count_active_entries(self) -> int:
        """Count total active Blackboard entries for the report."""
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.blackboard_entries
                    WHERE status NOT IN ('resolved', 'abandoned')
                    """
                )
            )
            return result.scalar() or 0
