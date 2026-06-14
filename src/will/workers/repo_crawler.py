# src/will/workers/repo_crawler.py
"""
Repo Crawler Worker — structural self-model builder.

- Declaration:  .intent/workers/repo_crawler.yaml
- Class:        sensing
- Phase:        audit
- Schedule:     max_interval=86400s, glide_off=8640s (10% default)

Responsibilities (one per run):
  1. Delegate full crawl orchestration to CrawlService.run_crawl().
  2. Post blackboard report with summary stats.

Crawl logic (scope config, call-graph extraction, artifact registration)
now lives in body.services.crawl_service and is imported here for
backward-compatibility access via this module's namespace.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

# Re-exported from crawl_service so any code that previously imported these
# from this module continues to resolve them without changes.
from shared.logger import getLogger
from shared.workers.base import Worker


logger = getLogger(__name__)


# ID: f1a2b3c4-d5e6-7890-abcd-ef1234567891
class RepoCrawlerWorker(Worker):
    """
    Sensing worker. Delegates crawl orchestration to CrawlService.run_crawl()
    and posts the result to the blackboard.
    """

    declaration_name = "repo_crawler"

    def __init__(self, cognitive_service: Any = None) -> None:
        from shared.infrastructure.bootstrap_registry import BootstrapRegistry

        super().__init__()
        self._cognitive_service = cognitive_service
        self._repo_root: Path = BootstrapRegistry.get_repo_path()
        schedule = self._declaration.get("mandate", {}).get("schedule", {})
        self._max_interval: int = schedule.get("max_interval", 86400)
        self._glide_off: int = schedule.get(
            "glide_off", max(int(self._max_interval * 0.10), 10)
        )

    # ID: ec3e046d-7df4-4e47-b34b-973f8bbe617f
    async def run_loop(self) -> None:
        """
        Continuous self-scheduling loop. Runs one crawl pass per
        max_interval seconds.
        """
        logger.info(
            "RepoCrawlerWorker: starting loop (max_interval=%ds, glide_off=%ds)",
            self._max_interval,
            self._glide_off,
        )

        await self._register()

        while True:
            cycle_start = time.monotonic()
            try:
                await self.run()
            except Exception as exc:
                logger.error("RepoCrawlerWorker: cycle failed: %s", exc, exc_info=True)
                try:
                    await self._post_entry(
                        entry_type="report",
                        subject="repo_crawler.cycle_error",
                        payload={"error": str(exc)},
                        status="abandoned",
                    )
                except Exception:
                    logger.exception("RepoCrawlerWorker: failed to post error report")

            elapsed = time.monotonic() - cycle_start
            await __import__("asyncio").sleep(max(self._max_interval - elapsed, 0))

    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678903
    async def run(self) -> None:
        """Crawl repository — delegate to CrawlService.run_crawl."""
        await self.post_heartbeat()
        from body.services.service_registry import service_registry

        logger.info("RepoCrawlerWorker: starting crawl pass")
        svc = await service_registry.get_crawl_service()
        stats = await svc.run_crawl(self._repo_root, self._cognitive_service)

        completed_at = datetime.now(UTC).isoformat()

        # ADR-070 D8 writer-as-sensor: emit a coherence.repo_artifacts.drift
        # finding when this cycle either reaped orphans (status=resolved) or
        # skipped the reap because a safety guard tripped (status=open). The
        # two cases are mutually exclusive: the orchestrator either runs the
        # DELETE inline OR records the guard state and leaves orphans_reaped
        # at 0. The worker reads stats and posts the appropriate shape.
        orphans_reaped = stats.get("orphans_reaped", 0)
        guard_raw = stats.get("coherence_guard")
        guard: dict[str, Any] = guard_raw if isinstance(guard_raw, dict) else {}

        if guard.get("triggered"):
            # Safety rail tripped — reap was SKIPPED. Post an OPEN finding
            # so a governor inspects the candidate list before any rows
            # are removed. This is the "system noticed and stopped" signal.
            await self._post_entry(
                entry_type="finding",
                subject="coherence.repo_artifacts.drift",
                payload={
                    "rule_id": "coherence.repo_artifacts.drift",
                    "severity": "high",
                    "drift_class": "excessive_or_partial_walk",
                    "trigger": guard.get("trigger"),
                    "proposed_reaps": guard.get("proposed_reaps"),
                    "total_known": guard.get("total_known"),
                    "total_walked": guard.get("total_walked"),
                    "walk_floor_required": guard.get("walk_floor_required"),
                    "reap_hard_cap": guard.get("reap_hard_cap"),
                    "reap_fraction_cap": guard.get("reap_fraction_cap"),
                    "sample_paths": guard.get("sample_paths", []),
                    "remediation": "skipped",
                    "remediation_hint": (
                        "Reap exceeded the ADR-070 D8 safety bound. "
                        "Inspect the candidate list before any rows "
                        "are removed. If the candidates are legitimate "
                        "(e.g. a large refactor deleting many files), "
                        "delete them manually via SQL. If a config "
                        "issue (narrowed crawl scope, missing mount), "
                        "restore the source-of-truth state before the "
                        "next cycle."
                    ),
                    "detected_at": completed_at,
                    "pair_id": "repo_artifacts ↔ filesystem",
                },
                status="open",
            )
        elif orphans_reaped > 0:
            # Normal inline reap completed — record audit-trail attribution
            # with status=resolved (the writer handled remediation in-cycle,
            # ADR-070 D4 inline-remediation pattern).
            await self._post_entry(
                entry_type="finding",
                subject="coherence.repo_artifacts.drift",
                payload={
                    "rule_id": "coherence.repo_artifacts.drift",
                    "severity": "medium",
                    "drift_class": "reaped_inline",
                    "orphan_count": orphans_reaped,
                    "remediation": "inline-reap",
                    "remediated_at": completed_at,
                    "pair_id": "repo_artifacts ↔ filesystem",
                },
                status="resolved",
            )

        await self.post_report(
            subject="repo.crawl.complete",
            payload={
                **stats,
                "completed_at": completed_at,
            },
        )
        logger.info("RepoCrawlerWorker: crawl complete — %s", stats)
