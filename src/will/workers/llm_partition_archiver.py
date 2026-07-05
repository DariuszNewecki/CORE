# src/will/workers/llm_partition_archiver.py
"""LLM Exchange Log Partition Archiver (ADR-052 §gxp-retention).

Moves llm_exchange_log partitions older than the configured retention window
to core_archive schema, satisfying EU Annex 11 GxP traceability requirements.

GxP invariant: partitions are NEVER dropped — only moved. Archived partitions
remain queryable in core_archive indefinitely.

The action (log.archive_partitions, Body layer) owns the system_config read for
log_retention_months. This worker is pure orchestration — it delegates all DB
access to the action via ActionExecutor.

CONSTITUTIONAL:
- Declaration:  .intent/workers/llm_partition_archiver.yaml
- Class:        governance (deterministic scheduler, no LLM)
- Phase:        execution — delegates to log.archive_partitions action
- Permitted:    log.archive_partitions
- Approval:     false — action carries its own governance (impact: moderate)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.workers.base import Worker


if TYPE_CHECKING:
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: aeb10c84-9fa8-4a32-b268-3ab6eca8a1c6
class LlmPartitionArchiverWorker(Worker):
    """ADR-052 GxP retention — moves old llm_exchange_log partitions to core_archive.

    Delegates to log.archive_partitions via ActionExecutor with write=True.
    The action reads log_retention_months from system_config (defaults to 24).
    Posts a report on success; posts a finding on failure. Always posts a heartbeat.
    """

    declaration_name = "llm_partition_archiver"

    def __init__(self, core_context: CoreContext) -> None:
        super().__init__(declaration_name=self.declaration_name)
        self._core_context = core_context

    # ID: f996a217-158d-49ea-92d4-9f938538f82f
    async def run(self) -> None:
        """Execute one archival cycle: move old partitions to core_archive schema."""
        from body.atomic.executor import ActionExecutor

        await self.post_heartbeat()

        executor = ActionExecutor(self._core_context)
        try:
            result = await executor.execute("log.archive_partitions", write=True)
        except Exception as exc:
            logger.error(
                "LlmPartitionArchiverWorker: log.archive_partitions raised: %s",
                exc,
                exc_info=True,
            )
            await self.post_finding(
                "log.partition_archival.failed",
                {
                    "error": str(exc),
                    "severity": "high",
                    "message": (
                        "llm_exchange_log partition archival failed — "
                        "GxP retention compliance may be at risk (ADR-052)"
                    ),
                },
            )
            return

        if not result.ok:
            errors = result.data.get("errors", [])
            await self.post_finding(
                "log.partition_archival.failed",
                {
                    "errors": errors,
                    "severity": "high",
                    "message": (
                        f"One or more partitions could not be archived "
                        f"({len(errors)} error(s)) — verify DB connectivity (ADR-052)"
                    ),
                },
            )
            logger.error("LlmPartitionArchiverWorker: archival errors: %s", errors)
            return

        archived = result.data.get("archived", [])
        await self.post_report(
            "log.partition_archival.complete",
            {
                "archived": archived,
                "archived_count": len(archived),
                "retention_months": result.data.get("retention_months"),
                "cutoff": result.data.get("cutoff"),
            },
        )
        if archived:
            logger.info(
                "LlmPartitionArchiverWorker: archived %d partition(s): %s",
                len(archived),
                archived,
            )
        else:
            logger.debug(
                "LlmPartitionArchiverWorker: no partitions older than %s to archive",
                result.data.get("cutoff"),
            )
