# src/mind/logic/engines/workflow_gate/checks/alignment.py
# ID: 3ab94efd-091c-4072-b0e0-406dbe0505ae

"""
Alignment verification workflow check.
Refactored to be circular-safe and constitutionally compliant.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import text

from mind.logic.engines.workflow_gate.base_check import WorkflowCheck
from shared.logger import getLogger
from shared.path_resolver import PathResolver


logger = getLogger(__name__)


# ID: 973aa73f-3f20-402f-b382-06af2686b3ae
class AlignmentVerificationCheck(WorkflowCheck):
    """Verifies that AlignmentOrchestrator successfully healed the file."""

    check_type = "alignment_verification"

    def __init__(self, path_resolver: PathResolver) -> None:
        self._paths = path_resolver

    # ID: d54fca88-5c46-45a1-82ef-028993cd3af4
    async def verify(self, file_path: Path | None, params: dict[str, Any]) -> list[str]:
        """
        Verify alignment status by checking current violations and DB audit history.
        """
        if not file_path:
            return []

        # DEFERRED IMPORT: Required to break circular dependency with Mind layer discovery
        from mind.governance.audit_context import AuditorContext
        from mind.governance.filtered_audit import run_filtered_audit

        violations = []

        # 1. Internal Sensation: Check current compliance state
        # Uses the repository root from the path resolver
        auditor_ctx = AuditorContext(self._paths.repo_root)

        # Run targeted audit logic
        findings, _, _ = await run_filtered_audit(auditor_ctx, rule_patterns=[r".*"])
        file_violations = [f for f in findings if f.get("file_path") == str(file_path)]

        if file_violations:
            violations.append(f"File has {len(file_violations)} outstanding violations")

        # 2. External Sensation: Query the Body's Ledger (Database)
        context = params.get("_context")
        session = getattr(context, "db_session", None)

        if not session:
            logger.warning("AlignmentCheck: Database session unavailable in context.")
            # We don't block if DB is missing, but we report the sensory gap
            violations.append(
                "System Sensation Error: Action Ledger (DB) is currently unreachable."
            )
            return violations

        try:
            # Query the action_results table using the provided session
            stmt = text(
                """
                SELECT ok
                FROM core.action_results
                WHERE action_type = 'alignment'
                  AND file_path = :p
                ORDER BY created_at DESC
                LIMIT 1
                """
            )
            result = await session.execute(stmt, {"p": str(file_path)})
            row = result.fetchone()

            if row and not row[0]:
                violations.append(
                    "The last automated alignment attempt for this file failed."
                )

        except Exception as e:
            logger.error("Failed to query action ledger for %s: %s", file_path, e)
            violations.append(f"Database Query Error: {e}")

        return violations
