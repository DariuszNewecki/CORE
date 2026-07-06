# src/body/introspection/drift_service.py
"""
Symbols-drift service — ADR-143 D3.

Queries existing blackboard findings and DB state instead of re-scanning source.
Detection is owned by purity.stable_id_anchor audit rule + fix.ids remediation loop.
"""

from __future__ import annotations

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)

_ANCHOR_SUBJECT_LIKE = "python::purity.stable_id_anchor::%"


# ID: 51f59218-c7f5-41ae-b2c9-87d4459e14d2
async def run_drift_analysis_async() -> dict:
    """Query existing pipeline data for symbols-drift status (ADR-143 D3).

    Returns anchor_violations (open purity.stable_id_anchor findings),
    pending_symbols (core.symbols rows pending classification), and
    last_sync_at (most recent DbSyncWorker heartbeat timestamp).
    Does not re-scan source — consumes governed pipeline output only.
    """
    from body.services.service_registry import ServiceRegistry

    try:
        async with ServiceRegistry.session() as session:
            anchor_result = await session.execute(
                text(
                    """
                    SELECT COUNT(*) FROM core.blackboard_entries
                    WHERE entry_type = 'finding'
                      AND subject LIKE :like_pattern
                      AND status NOT IN (
                          'resolved', 'abandoned', 'suppressed',
                          'dry_run_complete', 'deferred_to_proposal', 'indeterminate'
                      )
                    """
                ),
                {"like_pattern": _ANCHOR_SUBJECT_LIKE},
            )
            open_anchor_violations = int(anchor_result.scalar() or 0)

            pending_result = await session.execute(
                text(
                    "SELECT COUNT(*) FROM core.symbols"
                    " WHERE definition_status = 'pending'"
                )
            )
            pending_symbols = int(pending_result.scalar() or 0)

            hb_result = await session.execute(
                text(
                    """
                    SELECT created_at FROM core.blackboard_entries
                    WHERE entry_type = 'heartbeat'
                      AND subject = 'worker.heartbeat'
                      AND payload->>'worker' = 'db_sync_worker'
                    ORDER BY created_at DESC
                    LIMIT 1
                    """
                )
            )
            hb_row = hb_result.fetchone()
            last_sync_at = hb_row[0].isoformat() if hb_row and hb_row[0] else None

        return {
            "available": True,
            "anchor_violations": open_anchor_violations,
            "pending_symbols": pending_symbols,
            "last_sync_at": last_sync_at,
        }
    except Exception as exc:
        logger.warning("drift_service: symbols query failed: %s", exc)
        return {
            "available": False,
            "error": f"{type(exc).__name__}: {exc}",
        }
