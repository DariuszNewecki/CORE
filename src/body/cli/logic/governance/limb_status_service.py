# src/body/cli/logic/governance/limb_status_service.py
# ID: a1b2c3d4-e5f6-7890-abcd-ef1234567810

"""
Limb Status Service - Phase 3 Hardening.
Summarizes recent limb operations to highlight system-wide issues.

CONSTITUTIONAL COMPLIANCE:
- logic.di.no_global_session: Session factory is injected via __init__.
- logic.logging.standard_only: Uses getLogger, no Rich/Console usage.
- architecture.boundary.settings_access: No direct settings import.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from sqlalchemy import text

from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 56a20121-fe6c-4747-bd59-4021fd455df6
class LimbStatusService:
    """
    Analyzes the Body's action ledger to provide a forensic health summary.
    """

    def __init__(self, session_factory: Callable):
        """
        Constitutional DI: Receives factory, does not import globals.
        """
        self.session_factory = session_factory

    # ID: 30c15118-63c5-4356-9586-e254a8cb8ff1
    async def get_recent_limb_health(self, limit: int = 15) -> dict[str, Any]:
        """
        Queries the action_results table and groups failing patterns.
        """
        async with self.session_factory() as session:
            # Sensation: Pull the most recent operational evidence
            query = text(
                """
                SELECT action_type, ok, error_message, created_at
                FROM core.action_results
                ORDER BY created_at DESC
                LIMIT :limit
            """
            )
            res = await session.execute(query, {"limit": limit})
            actions = res.mappings().all()

        if not actions:
            return {"status": "unknown", "issues": []}

        # Logic: Detect failing neurons
        issues = []
        failures = 0
        for a in actions:
            if not a["ok"]:
                failures += 1
                issues.append(
                    {
                        "action": a["action_type"],
                        "error": a["error_message"] or "Policy Warning",
                        "time": a["created_at"],
                    }
                )

        return {
            "total_checked": len(actions),
            "failure_count": failures,
            "status": "OPTIMAL" if failures == 0 else "DEGRADED",
            "issues": issues,
        }
