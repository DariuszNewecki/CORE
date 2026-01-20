# src/mind/logic/engines/workflow_gate/checks/audit.py

"""
Audit history workflow check.

Verifies audit history shows consistent compliance (no recent violations).

CONSTITUTIONAL FIX:
- Uses service_registry.session() instead of get_session()
- Mind layer receives session factory from Body layer
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: e5f6a7b8-c9d0-1e2f-3a4b-5c6d7e8f9a0b
class AuditHistoryCheck(WorkflowCheck):
    """
    Verifies audit history shows consistent compliance.

    Checks for recent violations in the past 7 days.
    """

    check_type = "audit_history"

    # ID: ab347ede-0a23-4e60-9370-dd52710f6107
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Verify no recent audit violations.

        Args:
            file_path: Unused (context-level check)
            params: Check parameters (currently unused)

        Returns:
            List of violations if recent failures found
        """
        # CONSTITUTIONAL FIX: Use service_registry.session() instead of get_session()
        from body.services.service_registry import service_registry

        async with service_registry.session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM core.audit_runs
                    WHERE passed = false
                    AND started_at > NOW() - INTERVAL '7 days'
                    """
                )
            )
            failed_count = result.scalar_one()

            if failed_count > 0:
                return [
                    f"Found {failed_count} failed audit(s) in the past 7 days. System must maintain compliance."
                ]

            return []
