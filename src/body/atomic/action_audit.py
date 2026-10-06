# src/body/atomic/action_audit.py
"""
Action audit-trail persistence for the ActionExecutor gateway.

Moved verbatim out of ``ActionExecutor._audit_log`` (ADR-095 split of the
too-large executor class; zero behavior change). ``ActionAuditRecorder``
writes one ``core.action_results`` row per executed action — step 7 of
``ActionExecutor.execute`` — with bounded retry/backoff, and surfaces an
``AUDIT_GAP`` error for write actions whose row could not be persisted.

This module defines no atomic action and never invokes ``ActionExecutor``;
it is a plain persistence helper the executor delegates to.
"""

from __future__ import annotations

import asyncio
import json
from typing import TYPE_CHECKING

from sqlalchemy import text

from shared.logger import _current_run_id, getLogger


if TYPE_CHECKING:
    from body.atomic.registry import ActionDefinition
    from shared.action_types import ActionResult
    from shared.context import CoreContext

logger = getLogger(__name__)


# ID: 7c763fc4-5116-4ad9-a05d-761811083559
class ActionAuditRecorder:
    """Persists ActionExecutor results to the core.action_results audit trail."""

    _AUDIT_MAX_ATTEMPTS: int = 3
    _AUDIT_BACKOFF_BASE_SEC: float = 0.1  # doubled each retry: 0.1s, 0.2s

    def __init__(self, core_context: CoreContext):
        self.core_context = core_context

    # ID: 454c8ccb-ece8-4ef8-baf1-13c9c19f4300
    async def record(
        self, definition: ActionDefinition, result: ActionResult, write: bool
    ) -> None:
        """
        Log action execution to database audit trail (SSOT).

        Retries the INSERT up to _AUDIT_MAX_ATTEMPTS times with exponential
        backoff before declaring an AUDIT_GAP. Each attempt opens a fresh
        session so a rolled-back transaction from a prior attempt does not
        poison the retry.

        CONSTITUTIONAL FIX: session_id is read cleanly from _current_run_id
        context var (imported at module level). Removed duplicate key and
        broken __import__ hack from prior patch.
        """
        stmt = text(
            """
            INSERT INTO core.action_results
            (action_type, ok, file_path, error_message, action_metadata, agent_id, duration_ms)
            VALUES (:atype, :ok, :path, :err, :meta, :agent, :dur)
            """
        )
        # Prefer session_id from core_context, fall back to context var
        session_id = getattr(
            self.core_context, "session_id", None
        ) or _current_run_id.get(None)
        params = {
            "atype": definition.action_id,
            "ok": result.ok,
            "path": result.data.get("path") or result.data.get("file_path"),
            "err": result.data.get("error") if not result.ok else None,
            "meta": json.dumps(
                {
                    "write_mode": write,
                    "impact": definition.impact_level,
                    "session_id": session_id,
                }
            ),
            "agent": "ActionExecutor",
            "dur": int(result.duration_sec * 1000),
        }

        last_exc: Exception | None = None
        for attempt in range(1, self._AUDIT_MAX_ATTEMPTS + 1):
            try:
                async with self.core_context.registry.session() as session:
                    async with session.begin():
                        await session.execute(stmt, params)
                return  # persisted successfully
            except Exception as e:
                last_exc = e
                if attempt < self._AUDIT_MAX_ATTEMPTS:
                    await asyncio.sleep(
                        self._AUDIT_BACKOFF_BASE_SEC * (2 ** (attempt - 1))
                    )

        # All attempts exhausted — #634/#752: surface LOUD for write actions.
        # Audit persistence runs at step 7 after the mutation has already
        # landed; there is no file+DB transaction to unwind. On DB
        # unavailability/serialization failure only (schema has no per-row
        # failure mode — action_type/ok are always supplied).
        assert last_exc is not None
        if write:
            logger.error(
                "AUDIT_GAP: write action %s executed but its "
                "core.action_results row failed to persist after %d attempts "
                "(%s) — mutation stands, audit trail incomplete (#634/#752)",
                definition.action_id,
                self._AUDIT_MAX_ATTEMPTS,
                last_exc,
            )
        else:
            logger.warning(
                "Non-blocking audit log failure (read) after %d attempts: %s",
                self._AUDIT_MAX_ATTEMPTS,
                last_exc,
            )
