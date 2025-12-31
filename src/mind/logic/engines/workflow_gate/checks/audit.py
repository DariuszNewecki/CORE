# src/mind/logic/engines/workflow_gate/checks/audit.py

"""
Audit history workflow check.

Verifies audit history shows consistent compliance (no recent violations).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.infrastructure.database.session_manager import get_session
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
            file_path: File to check history for
            params: May include 'max_recent_violations' threshold

        Returns:
            List of violations if file has too many recent issues
        """
        if not file_path:
            return []

        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT COUNT(*)
                    FROM core.audit_findings
                    WHERE file_path = :file_path
                    AND created_at > NOW() - INTERVAL '7 days'
                    AND severity IN ('error', 'critical')
                """
                ),
                {"file_path": str(file_path)},
            )
            count = result.scalar()

            max_violations = params.get("max_recent_violations", 3)
            if count and count > max_violations:
                return [
                    f"File has {count} violations in past 7 days (threshold: {max_violations}). "
                    "Indicates structural instability."
                ]
            return []
