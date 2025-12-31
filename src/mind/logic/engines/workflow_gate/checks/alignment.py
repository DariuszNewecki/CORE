# src/mind/logic/engines/workflow_gate/checks/alignment.py

"""
Alignment verification workflow check.

Verifies that AlignmentOrchestrator successfully healed the file.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.config import settings
from shared.infrastructure.database.session_manager import get_session
from shared.logger import getLogger


logger = getLogger(__name__)


# ID: d4e5f6a7-b8c9-0d1e-2f3a-4b5c6d7e8f9a
class AlignmentVerificationCheck(WorkflowCheck):
    """
    Verifies that AlignmentOrchestrator successfully healed the file.

    Checks both constitutional compliance and alignment action status.
    """

    check_type = "alignment_verification"

    # ID: 321a4b92-dbd0-48cf-9575-02c9b7369874
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Verify file alignment status.

        Args:
            file_path: File to check alignment for
            params: Check parameters (currently unused)

        Returns:
            List of violations if alignment failed or file has violations
        """
        if not file_path:
            return []

        from mind.governance.audit_context import AuditorContext
        from mind.governance.filtered_audit import run_filtered_audit

        violations = []

        # Check 1: Constitutional compliance
        auditor_ctx = AuditorContext(settings.REPO_PATH)
        findings, _, _ = await run_filtered_audit(auditor_ctx, rule_patterns=[r".*"])

        file_violations = [
            f
            for f in findings
            if f.get("file_path") == str(file_path)
            and "engine_missing" not in str(f.get("check_id"))
        ]

        if file_violations:
            violations.append(
                f"File has {len(file_violations)} outstanding constitutional violations"
            )

        # Check 2: Recent alignment action status
        async with get_session() as session:
            result = await session.execute(
                text(
                    """
                    SELECT ok, error_message
                    FROM core.action_results
                    WHERE action_type = 'alignment'
                    AND action_metadata->>'file_path' = :file_path
                    ORDER BY created_at DESC
                    LIMIT 1
                """
                ),
                {"file_path": str(file_path)},
            )
            row = result.fetchone()

            if row and not row[0]:
                violations.append(f"Last alignment attempt failed: {row[1]}")

        return violations
