# src/will/governance/sync_runner.py

"""
Sync runner facade — Will-layer entry point for the /sync API
(ADR-058 D2).

Four sync operations share a single `core.sync_runs` table, distinguished
by `sync_type`:

* `knowledge_graph`  → atomic action `sync.db`         (CLI command tree → DB)
* `vectors`      → atomic action `sync.vectors_constitution`
* `code_vectors` → atomic action `sync.vectors_code`
* `dev_sync`     → `will.workflows.DevSyncWorkflow.run` (composite)

Atomic-action paths dispatch through `ActionExecutor` — the same Will
facade pattern `fix_runner` uses. The `dev_sync` composite uses
`DevSyncWorkflow` directly because it orchestrates a fix → knowledge-graph →
vectors sequence whose result shape is per-phase, not per-action.
"""

from __future__ import annotations

import json
from typing import Any
from uuid import UUID

from sqlalchemy import text

from shared.context import CoreContext
from shared.logger import getLogger
from shared.workers.blackboard_publisher import _sanitize_payload


__all__ = [
    "ALLOWED_SYNC_TYPES",
    "run_and_persist_sync",
]


logger = getLogger(__name__)


ALLOWED_SYNC_TYPES = frozenset(
    {"knowledge_graph", "vectors", "code_vectors", "dev_sync"}
)


_SYNC_TYPE_TO_ACTION_ID = {
    "knowledge_graph": "sync.db",
    "vectors": "sync.vectors_constitution",
    "code_vectors": "sync.vectors_code",
}


# ID: 2c9e6d4f-8b3a-4d0c-e7f8-1a2b3c4d5e67
async def _update_sync_run_status(
    session: Any,
    run_id: UUID,
    status: str,
    *,
    started: bool = False,
    finished: bool = False,
    error: str | None = None,
    result: dict | None = None,
) -> None:
    """Update a sync_runs row's lifecycle state. Each call commits."""
    sets = ["status = :status"]
    params: dict[str, Any] = {"status": status, "rid": run_id}

    if started:
        sets.append("started_at = now()")
    if finished:
        sets.append("finished_at = now()")
    if error is not None:
        sets.append("error = :err")
        params["err"] = error
    if result is not None:
        sets.append("result = cast(:result as jsonb)")
        params["result"] = json.dumps(_sanitize_payload(result), default=str)

    await session.execute(
        text(f"UPDATE core.sync_runs SET {', '.join(sets)} WHERE id = :rid"),
        params,
    )
    await session.commit()


# ID: 3d0f7e5a-9c4b-4e1d-f8a9-2b3c4d5e6f78
async def run_and_persist_sync(
    context: CoreContext,
    session: Any,
    *,
    run_id: UUID,
    sync_type: str,
    write: bool,
    target: str | None = None,
    force: bool = False,
) -> None:
    """Dispatch the correct backend per `sync_type` and persist on sync_runs.

    The row has been INSERTed by the route handler with status='pending'
    and the supplied `sync_type` / `write` / `target` values. This
    function transitions it through executing → completed | failed.

    `force` is a runtime parameter (not persisted on sync_runs): it is
    forwarded to the backend action where supported. `sync.vectors_code`
    uses it to reset chunk_count on already-embedded artifacts before
    the embed loop.

    Errors are caught and recorded on the row; this function never
    raises into the background-task scheduler.
    """
    await _update_sync_run_status(session, run_id, "executing", started=True)

    try:
        if sync_type == "dev_sync":
            from will.workflows.dev_sync_workflow import DevSyncWorkflow

            workflow = DevSyncWorkflow(context)
            workflow_result = await workflow.run(write=write)
            ok = bool(getattr(workflow_result, "ok", False))
            result_payload = (
                workflow_result.model_dump(mode="json")
                if hasattr(workflow_result, "model_dump")
                else {"raw": str(workflow_result)}
            )
        else:
            action_id = _SYNC_TYPE_TO_ACTION_ID.get(sync_type)
            if action_id is None:
                await _update_sync_run_status(
                    session,
                    run_id,
                    "failed",
                    finished=True,
                    error=f"Unknown sync_type: {sync_type!r}",
                )
                return

            from body.atomic.executor import ActionExecutor

            executor = ActionExecutor(context)
            exec_kwargs: dict[str, Any] = {}
            if target is not None:
                exec_kwargs["target"] = target
            # force is only meaningful for sync.vectors_code (re-embed).
            # The other actions don't accept a `force` kwarg.
            if force and sync_type == "code_vectors":
                exec_kwargs["force"] = True
            action_result = await executor.execute(
                action_id, write=write, **exec_kwargs
            )
            ok = bool(action_result.ok)
            result_payload = {
                "ok": action_result.ok,
                "data": action_result.data,
                "duration_sec": action_result.duration_sec,
                "action_id": action_id,
            }
    except Exception as exc:
        logger.exception("sync_runner: %s raised for %s", sync_type, run_id)
        await _update_sync_run_status(
            session,
            run_id,
            "failed",
            finished=True,
            error=f"{type(exc).__name__}: {exc}",
        )
        return

    await _update_sync_run_status(
        session,
        run_id,
        "completed" if ok else "failed",
        finished=True,
        error=None if ok else "operation reported ok=False",
        result=result_payload,
    )

    logger.info(
        "sync_runner: %s (%s) completed ok=%s write=%s force=%s",
        run_id,
        sync_type,
        ok,
        write,
        force,
    )
