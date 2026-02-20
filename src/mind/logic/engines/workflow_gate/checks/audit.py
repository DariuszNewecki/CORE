# src/mind/logic/engines/workflow_gate/checks/audit.py
# ID: 7ecd19f0-ba00-4786-a641-4d5949bdefc1

"""
Audit history workflow check.

Verifies audit history shows consistent compliance (no recent violations).

CONSTITUTIONAL ALIGNMENT (V2.6.0):
- Purified: Removed direct Body-layer import (service_registry) to resolve
  architecture.mind.no_body_invocation.
- Inversion of Control: Uses the database session provided in the evaluation
  context instead of managing its own connection.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: 3ffd4b42-aa0d-4fd0-9912-172e1d19b63d
class AuditHistoryCheck(WorkflowCheck):
    """
    Verifies audit history shows consistent compliance.

    Checks for recent violations in the past 7 days.
    """

    check_type = "audit_history"

    # ID: ab347ede-0a23-4e60-9370-dd52710f6107
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Verify no recent audit violations via the provided database context.

        Args:
            file_path: Unused (context-level check)
            params: Must contain '_context' with an active 'db_session'
        """
        # CONSTITUTIONAL FIX: Extract the session from the context provided in params.
        # This complies with the "Mind Never Invokes Body" law.
        context = params.get("_context")
        session = getattr(context, "db_session", None)

        if not session:
            logger.warning(
                "AuditHistoryCheck: Database session unavailable in context."
            )
            # If the Body failed to provide a session, we report a sensory gap.
            return ["System Sensation Error: Audit Ledger (DB) is unreachable."]

        try:
            # Query the audit_runs table for failures in the last 7 days.
            # This is a read-only evaluation of system history.
            stmt = text(
                """
                SELECT COUNT(*)
                FROM core.audit_runs
                WHERE passed = false
                AND started_at > NOW() - INTERVAL '7 days'
                """
            )

            result = await session.execute(stmt)
            failed_count = result.scalar_one()

            if failed_count > 0:
                return [
                    f"Found {failed_count} failed audit(s) in the past 7 days. "
                    "The system must maintain consistent constitutional compliance."
                ]

            return []

        except Exception as e:
            logger.error("Failed to query audit history: %s", e)
            return [f"Database Query Error: {e}"]
