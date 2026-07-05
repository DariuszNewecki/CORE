# src/will/workers/llm_partition_maintainer.py
"""LLM Exchange Log Partition Maintainer (ADR-052 §partition-maintenance).

Ensures upcoming monthly partitions of core.llm_exchange_log are created
ADVANCE_MONTHS ahead of time so the append-only audit log never becomes
unwritable due to a missing partition.

ADR-052 mandates that the next month's partition exist before the month begins.
The worker runs every 6 hours — far more frequently than strictly needed — so
any gap from a missed-creation cycle heals quickly. The underlying action is
idempotent: re-creating an existing partition is a no-op.

CONSTITUTIONAL:
- Declaration:  .intent/workers/llm_partition_maintainer.yaml
- Class:        governance (deterministic scheduler, no LLM)
- Phase:        execution — delegates to log.maintain_partitions action
- Permitted:    log.maintain_partitions
- Approval:     false — action carries its own governance (impact: safe)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.workers.base import Worker


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: dfe70a98-68de-476d-9c91-0b7b1728cf92
class LlmPartitionMaintainerWorker(Worker):
    """ADR-052 partition maintenance — creates upcoming llm_exchange_log partitions.

    Delegates to log.maintain_partitions via ActionExecutor with write=True.
    Posts a report on success and a finding on failure. Always posts a heartbeat.
    """

    declaration_name = "llm_partition_maintainer"

    def __init__(self, core_context: CoreContext) -> None:
        super().__init__(declaration_name=self.declaration_name)
        self._core_context = core_context

    # ID: 1ff6e54c-b8c6-46fc-a9de-a44349c0aa7b
    async def run(self) -> None:
        """Execute one maintenance cycle: ensure next 3 months of partitions exist."""
        from body.atomic.executor import ActionExecutor

        await self.post_heartbeat()

        executor = ActionExecutor(self._core_context)
        try:
            result = await executor.execute("log.maintain_partitions", write=True)
        except Exception as exc:
            logger.error(
                "LlmPartitionMaintainerWorker: log.maintain_partitions raised: %s",
                exc,
                exc_info=True,
            )
            await self.post_finding(
                "log.partition_maintenance.failed",
                {
                    "error": str(exc),
                    "severity": "high",
                    "message": (
                        "llm_exchange_log partition maintenance failed — "
                        "future months may become unwritable (ADR-052)"
                    ),
                },
            )
            return

        if not result.ok:
            errors = result.data.get("errors", [])
            await self.post_finding(
                "log.partition_maintenance.failed",
                {
                    "errors": errors,
                    "severity": "high",
                    "message": (
                        "One or more llm_exchange_log partitions could not be created "
                        f"({len(errors)} error(s)) — check DB connectivity (ADR-052)"
                    ),
                },
            )
            logger.error(
                "LlmPartitionMaintainerWorker: partition creation errors: %s", errors
            )
            return

        created = result.data.get("created", [])
        skipped = result.data.get("skipped", [])
        await self.post_report(
            "log.partition_maintenance.complete",
            {
                "created": created,
                "skipped": skipped,
                "created_count": len(created),
                "skipped_count": len(skipped),
                "advance_months": result.data.get("advance_months", 3),
            },
        )
        if created:
            logger.info(
                "LlmPartitionMaintainerWorker: created %d partition(s): %s",
                len(created),
                created,
            )
        else:
            logger.debug(
                "LlmPartitionMaintainerWorker: all %d partition(s) already existed",
                len(skipped),
            )
