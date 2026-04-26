# src/will/workers/vector_sync_worker.py
# ID: will.workers.vector_sync_worker
"""
VectorSyncWorker - Qdrant Code-Vector Sync Worker.

Responsibility: Periodically execute the `sync.vectors.code` atomic action
so that the Qdrant code-vector index stays aligned with the source tree
without requiring an operator to run `core-admin dev sync --write`
manually.

The worker is a thin, deterministic wrapper. All work is delegated to
`body.atomic.sync_actions.action_sync_code_vectors` via ActionExecutor.
The worker contributes nothing of its own to the transformation — it is
a schedule + blackboard surface for an atomic action that already exists.

Constitutional standing:
- Declaration:      .intent/workers/vector_sync_worker.yaml
- Class:            sync
- Phase:            execution — delegates to a registered atomic action
- Permitted tools:  sync.vectors.code — atomic action delegate
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


# ID: 7b2e8c4f-1d96-4a83-b052-3f9e1c7d2a08
class VectorSyncWorker(Worker):
    """
    Sync worker. Wraps the `sync.vectors.code` atomic action so the Qdrant
    code-vector index is refreshed on a schedule rather than only on
    operator command.

    Posts `sync.vectors.code.complete` reports on success and
    `sync.vectors.code.failed` findings on failure. No LLM. No file writes.
    No blackboard claims.
    """

    declaration_name = "vector_sync_worker"

    def __init__(self, core_context: CoreContext) -> None:
        super().__init__(declaration_name=self.declaration_name)
        self._core_context = core_context

    # ID: 2c8d4f6a-9e51-4b73-80c5-6a1f3e9d7b42
    async def run(self) -> None:
        """
        Execute one sync cycle:
        1. Invoke `sync.vectors.code` via ActionExecutor with write=True,
           force=False.
        2. On success: post a `sync.vectors.code.complete` report with
           result.data.
        3. On failure: post a `sync.vectors.code.failed` finding with the
           error.
        4. Always post a heartbeat before returning.
        """
        from body.atomic.executor import ActionExecutor

        executor = ActionExecutor(self._core_context)

        try:
            result = await executor.execute(
                "sync.vectors.code", write=True, force=False
            )
        except Exception as exc:
            logger.error(
                "VectorSyncWorker: sync.vectors.code raised: %s", exc, exc_info=True
            )
            await self.post_finding(
                subject="sync.vectors.code.failed",
                payload={"error": str(exc)},
            )
            await self.post_heartbeat()
            return

        if result.ok:
            logger.info(
                "VectorSyncWorker: sync.vectors.code complete — %s", result.data
            )
            await self.post_report(
                subject="sync.vectors.code.complete",
                payload=result.data,
            )
        else:
            error = result.data.get("error") if isinstance(result.data, dict) else None
            logger.warning(
                "VectorSyncWorker: sync.vectors.code reported ok=False: %s", error
            )
            await self.post_finding(
                subject="sync.vectors.code.failed",
                payload={"error": error},
            )

        await self.post_heartbeat()
