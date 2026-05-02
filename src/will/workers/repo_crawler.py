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

    # ID: a1b2c3d4-e5f6-7890-abcd-ef1234567892
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

            await __import__("asyncio").sleep(self._max_interval)

    # ID: b2c3d4e5-f6a7-8901-bcde-f12345678903
    async def run(self) -> None:
        """Crawl repository — delegate to CrawlService.run_crawl."""
        await self.post_heartbeat()
        from body.services.service_registry import service_registry

        logger.info("RepoCrawlerWorker: starting crawl pass")
        svc = await service_registry.get_crawl_service()
        stats = await svc.run_crawl(self._repo_root, self._cognitive_service)

        await self.post_report(
            subject="repo.crawl.complete",
            payload={
                **stats,
                "completed_at": datetime.now(UTC).isoformat(),
            },
        )
        logger.info("RepoCrawlerWorker: crawl complete — %s", stats)
