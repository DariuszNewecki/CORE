# src/will/workers/db_sync_worker.py
# ID: will.workers.db_sync_worker
"""
DbSyncWorker - PostgreSQL Knowledge-Graph Sync Worker.

Responsibility: Periodically execute the `sync.db` atomic action so that
the PostgreSQL knowledge graph stays aligned with the source tree without
requiring an operator to run `core-admin dev sync --write` manually.

The worker is a thin, deterministic wrapper. All work is delegated to
`body.atomic.sync_actions.action_sync_database` via ActionExecutor. The
worker contributes nothing of its own to the transformation — it is a
schedule + blackboard surface for an atomic action that already exists.

Constitutional standing:
- Declaration:      .intent/workers/db_sync_worker.yaml
- Class:            sync
- Phase:            execution — delegates to a registered atomic action
- Permitted tools:  sync.db — atomic action delegate
- Approval:         false — atomic action carries its own governance

LAYER: will/workers — sync worker. Wraps a registered atomic action.
Posts findings/reports to Blackboard. No LLM. No file writes.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from shared.logger import getLogger
from shared.workers.base import Worker


if TYPE_CHECKING:
    from shared.context import CoreContext


logger = getLogger(__name__)


# ID: 4d7e1a2b-8c93-4f51-a067-2e8f9d3c1b0a
class DbSyncWorker(Worker):
    """
    Sync worker. Wraps the `sync.db` atomic action so the knowledge graph
    is refreshed on a schedule rather than only on operator command.

    Posts `sync.db.complete` reports on success and `sync.db.failed`
    findings on failure. No LLM. No file writes. No blackboard claims.
    """

    declaration_name = "db_sync_worker"

    def __init__(self, core_context: CoreContext) -> None:
        super().__init__(declaration_name=self.declaration_name)
        self._core_context = core_context

    # ID: 9a1f3c5d-2e84-4b67-90a3-7f1c8e5a2d4b
    async def run(self) -> None:
        """
        Execute one sync cycle:
        1. Invoke `sync.db` via ActionExecutor with write=True.
        2. On success: post a `sync.db.complete` report with result.data.
        3. On failure: post a `sync.db.failed` finding with the error.
        4. Always post a heartbeat before returning.
        """
        from body.atomic.executor import ActionExecutor

        executor = ActionExecutor(self._core_context)

        try:
            result = await executor.execute("sync.db", write=True)
        except Exception as exc:
            logger.error("DbSyncWorker: sync.db raised: %s", exc, exc_info=True)
            await self.post_finding(
                subject="sync.db.failed",
                payload={"error": str(exc)},
            )
            await self.post_heartbeat()
            return

        if result.ok:
            logger.info("DbSyncWorker: sync.db complete — %s", result.data)
            await self.post_report(
                subject="sync.db.complete",
                payload=result.data,
            )
        else:
            error = result.data.get("error") if isinstance(result.data, dict) else None
            logger.warning("DbSyncWorker: sync.db reported ok=False: %s", error)
            await self.post_finding(
                subject="sync.db.failed",
                payload={"error": error},
            )

        await self.post_heartbeat()
