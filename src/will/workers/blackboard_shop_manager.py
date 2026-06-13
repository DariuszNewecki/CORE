# src/will/workers/blackboard_shop_manager.py
"""
BlackboardShopManager - Blackboard Health Supervisory Worker.

Responsibility: Detect Blackboard entries that have exceeded their
constitutional SLA and post a finding for each stale unclaimed or
unresolved entry. Per ADR-082, also runs the writer-as-sensor
retention sweeps (terminal telemetry hard-DELETE + DELEGATE-class OPEN
finding status transition) as part of the same hygiene cycle.

Constitutional standing:
- Declaration:      .intent/workers/blackboard_shop_manager.yaml
- Class:            supervision
- Phase:            audit
- Permitted tools:  none — deterministic DB reads + bounded sweep writes
- Approval:         false — findings are observations only
- Schedule:         max_interval=600s

SLA tiers (seconds):
- heartbeat entries:  600   (10 minutes)
- finding entries:    3600  (1 hour)
- report entries:     7200  (2 hours)
- proposal entries:   1800  (30 minutes)
- default:            3600  (1 hour)

ADR-082 retention sweeps (per cycle, bounded by sweep_batch_max):
- Terminal telemetry: hard DELETE for subjects in
  blackboard.telemetry_subject_prefixes past telemetry_ttl_days.
- DELEGATE OPEN findings: status open → resolved for subjects in
  blackboard.delegate_finding_subjects past delegate_finding_ttl_days.

ADR-104 orphaned-claim reaper (per cycle, bounded by sweep_batch_max):
- Release claims held by workers no longer in the alive-set (ungraceful
  death). Released back to 'open' under the reclaim cap; abandoned
  (terminal) at the cap, with a Type-B blackboard.claim_orphan_abandoned::
  observation that surfaces as F-19 stuck. D5 fail-safe skips the sweep on
  an empty/unavailable alive-set. The D8 liveness lease (Worker.start)
  keeps long-running claim-holders in the alive-set so they are not reaped.

Self-scheduling: BlackboardShopManager manages its own asyncio loop via
run_loop(). Sanctuary starts run_loop() once on bootstrap.

LAYER: will/workers — supervisory worker. Reads Blackboard only.
Writes findings to Blackboard. No LLM. No file writes.

ADR-091 D2 Revision B resolution classification:
- Subject prefix:        blackboard.entry_stale::<entry_id>
- resolution_mechanism:  self_resolve
- Resolver path:         named delegate — BlackboardService's
                         resolve_stale_alerts_for_terminal_targets SQL
                         sweep (and the ADR-082 DELEGATE-class OPEN
                         finding TTL sweep above). The blackboard.entry_stale
                         finding is auto-resolved when its referenced
                         target entry itself reaches a terminal status.
                         This worker does NOT run an in-Python resolve
                         loop for its own findings; closure is delegated
                         to the named service.
- Not eligible for ADR-045 awaiting_reaudit: stale-entry alerts observe
  live runtime state of other Blackboard rows; there is no re-readable
  artifact for a sensor to re-evaluate against.
"""

from __future__ import annotations

import asyncio
import time
from typing import Any

from shared.infrastructure.intent.operational_config import load_operational_config
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
_CFG = load_operational_config().blackboard
_HEALTH = load_operational_config().health


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
            cycle_start = time.monotonic()
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

            elapsed = time.monotonic() - cycle_start
            await asyncio.sleep(max(self._max_interval - elapsed, 0))

    # -------------------------------------------------------------------------
    # Single audit cycle
    # -------------------------------------------------------------------------

    # ID: f6a7b8c9-e0f1-4a2b-3c4d-5e6f7a8b9c0d
    async def run(self) -> None:
        """
        Execute one Blackboard health cycle:
        1. Post heartbeat
        2. Auto-resolve stale-entry alerts whose target became terminal
        3. ADR-082 Mechanism 1: hard-DELETE terminal telemetry past TTL
        4. ADR-082 Mechanism 2: transition DELEGATE OPEN findings past TTL
        5. Fetch stale entries per SLA tier
        6. Post finding for each (deduplicated)
        7. Post completion report
        """
        await self.post_heartbeat()

        auto_resolved = await self._sweep_resolved_stale_alerts()
        if auto_resolved:
            logger.info(
                "BlackboardShopManager: auto-resolved %d stale alert(s) "
                "whose target reached terminal state",
                auto_resolved,
            )

        # #568: count-based retention replaces the time-based TTL for
        # slow-callback telemetry. The TTL sweep over-pruned well-behaved
        # workers (rare emitters lost their entire window) while leaving
        # hot emitters with hundreds of rows. Keep last N per subject.
        telemetry_swept = await self._sweep_telemetry_keep_last_n()
        if telemetry_swept:
            logger.info(
                "BlackboardShopManager: #568 telemetry sweep — deleted %d "
                "telemetry row(s) past keep-last-N-per-subject",
                telemetry_swept,
            )

        delegate_swept = await self._sweep_delegate_findings_ttl()
        if delegate_swept:
            logger.info(
                "BlackboardShopManager: ADR-082 DELEGATE sweep — resolved %d "
                "stale OPEN finding(s) past TTL",
                delegate_swept,
            )

        # ADR-104 — release claims orphaned by ungraceful worker death. Each
        # entry abandoned at the reclaim cap gets a terminal Type-B
        # observation so F19_CONVERGENCE_SQL counts it as stuck; released
        # entries are reported (not posted as findings, which would inflate
        # F-19's total_open — the very gauge ratification #3 protects).
        reaped = await self._sweep_orphaned_claims()
        for entry_id in reaped["abandoned"]:
            await self.post_observation(
                subject=f"blackboard.claim_orphan_abandoned::{entry_id}",
                payload={
                    "entry_id": entry_id,
                    "reason": "reclaim_cap_reached",
                    "reclaim_cap_n": _CFG.reclaim_cap_n,
                },
                status="abandoned",
            )
        if reaped["released"] or reaped["abandoned"]:
            logger.warning(
                "BlackboardShopManager: ADR-104 reaper — released %d orphaned "
                "claim(s), abandoned %d at reclaim cap",
                len(reaped["released"]),
                len(reaped["abandoned"]),
            )

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
                resolution_mechanism="self_resolve",
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
                "ttl_sweep": {
                    "telemetry_deleted": telemetry_swept,
                    "delegate_resolved": delegate_swept,
                },
                "orphan_reaper": {
                    "skipped": reaped["skipped"],
                    "released": len(reaped["released"]),
                    "abandoned": len(reaped["abandoned"]),
                    "released_ids": reaped["released"],
                    "abandoned_ids": reaped["abandoned"],
                },
            },
        )
        logger.info(
            "BlackboardShopManager: cycle complete — flagged=%d, telemetry_swept=%d, delegate_swept=%d",
            flagged,
            telemetry_swept,
            delegate_swept,
        )

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

    async def _sweep_resolved_stale_alerts(self) -> int:
        """Resolve stale-entry alerts whose target reached terminal state."""
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.resolve_stale_alerts_for_terminal_targets()

    async def _sweep_telemetry_ttl(self) -> int:
        """ADR-082 Mechanism 1 — hard-DELETE terminal telemetry past TTL.

        Retained but no longer invoked by run() — #568 replaced it with
        count-based retention (_sweep_telemetry_keep_last_n). Kept in
        place so consumers that may still reference it (tests, future
        telemetry families with TTL semantics) don't break.
        """
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.sweep_terminal_telemetry(
            subject_prefixes=_CFG.telemetry_subject_prefixes,
            ttl_days=_CFG.telemetry_ttl_days,
            batch_max=_CFG.sweep_batch_max,
        )

    async def _sweep_telemetry_keep_last_n(self) -> int:
        """#568 — keep last N samples per subject for slow-callback telemetry."""
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.sweep_telemetry_keep_last_n_per_subject(
            subject_prefixes=_CFG.telemetry_subject_prefixes,
            keep_last=_CFG.telemetry_keep_last_per_worker,
            batch_max=_CFG.sweep_batch_max,
        )

    async def _sweep_delegate_findings_ttl(self) -> int:
        """ADR-082 Mechanism 2 — open → resolved for stale DELEGATE findings."""
        from body.services.service_registry import service_registry

        svc = await service_registry.get_blackboard_service()
        return await svc.sweep_delegate_open_findings(
            subjects=_CFG.delegate_finding_subjects,
            ttl_days=_CFG.delegate_finding_ttl_days,
            batch_max=_CFG.sweep_batch_max,
        )

    async def _sweep_orphaned_claims(self) -> dict[str, Any]:
        """ADR-104 D1-D5 — release claims held by provably-dead workers.

        Orphan criteria (all three, evaluated in BlackboardService): the entry
        is 'claimed', its claimed_at is older than worker_alive_threshold_sec,
        and its claimed_by is not in the alive-set. Per ratification #2 the
        same threshold serves as both the liveness window and the claim grace
        (one clock). Releases under the reclaim cap; abandons at the cap (D3).

        D5 fail-safe: if the alive-set is unavailable or empty, skip this cycle
        rather than mass-reap on a transient registry glitch. Returns the
        BlackboardService result augmented with a 'skipped' flag; the caller
        posts terminal observations for abandoned entries and folds the counts
        into the run.complete report.
        """
        from body.services.service_registry import service_registry

        alive_threshold = _HEALTH.worker_alive_threshold_sec
        registry = await service_registry.get_worker_registry_service()
        try:
            alive = await registry.fetch_alive_workers(threshold_sec=alive_threshold)
        except Exception as exc:
            logger.warning(
                "BlackboardShopManager: ADR-104 reaper skipped — "
                "fetch_alive_workers failed: %s",
                exc,
            )
            return {"skipped": True, "released": [], "abandoned": []}

        live_uuids = [str(w["worker_uuid"]) for w in alive]
        if not live_uuids:
            logger.warning(
                "BlackboardShopManager: ADR-104 reaper skipped — empty "
                "alive-set (D5 fail-safe)"
            )
            return {"skipped": True, "released": [], "abandoned": []}

        svc = await service_registry.get_blackboard_service()
        result = await svc.release_orphaned_claims(
            live_uuids=live_uuids,
            grace_seconds=alive_threshold,
            reclaim_cap_n=_CFG.reclaim_cap_n,
            batch_max=_CFG.sweep_batch_max,
        )
        result["skipped"] = False
        return result
