# src/body/services/fix_run_service.py

"""
Persisted atomic-action execution service (ADR-154 D1).

The only sanctioned way for a Will-layer caller to get a *durable*
``core.fix_runs`` row out of an atomic-action run without holding a DB
session itself (``architecture.boundary.database_session_access`` — Will
MUST use DI, never import ``get_session``/``AsyncSession`` directly).

The existing ``/fix/run/{fix_id}`` API path (``api/v1/fix_routes.py`` +
``will/governance/fix_runner.run_and_persist_fix``) already does the
INSERT-then-persist sequence, but it is wired for a fire-and-forget
background task the caller polls for a result — it does not hand the
completed row's outcome back to its caller. RemediationCeremony's ADR-154
D1 gate needs the outcome *and* the durable ``validation_run_id``
synchronously, in one call, so ``build_validated_candidate`` can later
re-read exactly this row.

Kept intentionally narrow: this does not refactor the API path's
fire-and-forget flow (real, live, orthogonal). It duplicates the
``core.fix_runs`` INSERT/UPDATE SQL shape rather than importing
``will.governance.fix_runner`` — Body MUST NOT import Will
(``architecture.layers.no_body_to_will``).

Layer: body/services — infrastructure service, same pattern as
``validated_candidate_service.py`` (session via ``ServiceRegistry.session()``,
no LLM calls, no file writes).
"""

from __future__ import annotations

import json
from typing import TYPE_CHECKING, Any
from uuid import UUID

from sqlalchemy import text

from body.atomic.executor import ActionExecutor
from body.services.service_registry import service_registry
from shared.action_types import ActionResult
from shared.logger import getLogger


if TYPE_CHECKING:
    from shared.context import CoreContext


logger = getLogger(__name__)


# ID: 3e5eea1b-fea9-4345-b643-5080b1ecf7cb
async def submit_and_persist_fix(
    *,
    context: CoreContext,
    fix_id: str,
    write: bool,
    target_files: list[str] | None = None,
    params: dict[str, Any] | None = None,
    requested_by: str = "remediation_ceremony",
) -> tuple[str, ActionResult]:
    """Run an atomic action and persist it as a completed core.fix_runs row.

    INSERTs a ``status='pending'`` row, executes *fix_id* via
    ``ActionExecutor``, then UPDATEs the row to ``completed``/``failed``
    with the action's ``data``/``duration_sec`` — the same result shape
    ``run_and_persist_fix`` writes for the API path, so a row this function
    produces is indistinguishable, to a later reader, from one produced by
    ``POST /fix/run/{fix_id}``.

    Returns ``(run_id, action_result)`` — the durable row id (a
    ``build_validated_candidate(validation_run_id=...)`` call can re-read
    later) alongside the in-memory result for the caller's own immediate
    branching. Never raises: an action-execution exception is caught,
    persisted as a ``failed`` row, and surfaced as a synthetic
    ``ActionResult(ok=False, ...)`` rather than propagating — callers check
    ``action_result.ok`` uniformly, the same way every other collaborator
    in RemediationCeremony's ceremony reports failure.
    """
    async with service_registry.session() as session:
        insert_result = await session.execute(
            text(
                """
                INSERT INTO core.fix_runs
                    (kind, fix_id, target_files, write, status, requested_by)
                VALUES ('atomic', :fix_id, cast(:target_files as jsonb),
                        :write, 'pending', :requested_by)
                RETURNING id
                """
            ),
            {
                "fix_id": fix_id,
                "target_files": (
                    json.dumps(target_files) if target_files is not None else None
                ),
                "write": write,
                "requested_by": requested_by,
            },
        )
        run_id: UUID = insert_result.scalar_one()
        await session.commit()

        await session.execute(
            text(
                "UPDATE core.fix_runs SET status = 'executing', "
                "started_at = now() WHERE id = :rid"
            ),
            {"rid": run_id},
        )
        await session.commit()

        try:
            executor = ActionExecutor(context)
            exec_kwargs: dict[str, Any] = dict(params or {})
            if target_files is not None:
                exec_kwargs.setdefault("target_files", target_files)
            action_result = await executor.execute(fix_id, write=write, **exec_kwargs)
        except Exception as exc:
            logger.exception("fix_run_service: %s raised for %s", fix_id, run_id)
            exc_error_text = f"{type(exc).__name__}: {exc}"
            await session.execute(
                text(
                    "UPDATE core.fix_runs SET status = 'failed', "
                    "finished_at = now(), error = :err WHERE id = :rid"
                ),
                {"rid": run_id, "err": exc_error_text},
            )
            await session.commit()
            return str(run_id), ActionResult(
                action_id=fix_id, ok=False, data={"error": exc_error_text}
            )

        status = "completed" if action_result.ok else "failed"
        error_text = (
            None if action_result.ok else str(action_result.data.get("error", ""))
        )
        result_payload = {
            "kind": "atomic",
            "ok": action_result.ok,
            "data": action_result.data,
            "duration_sec": action_result.duration_sec,
        }

        await session.execute(
            text(
                "UPDATE core.fix_runs SET status = :status, finished_at = now(), "
                "error = :err, result = cast(:result as jsonb) WHERE id = :rid"
            ),
            {
                "rid": run_id,
                "status": status,
                "err": error_text,
                "result": json.dumps(result_payload, default=str),
            },
        )
        await session.commit()

    logger.info(
        "fix_run_service: %s (%s) completed status=%s ok=%s",
        run_id,
        fix_id,
        status,
        action_result.ok,
    )
    return str(run_id), action_result
