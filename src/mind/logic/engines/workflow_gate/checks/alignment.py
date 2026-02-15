# src/mind/logic/engines/workflow_gate/checks/alignment.py
# ID: 3ab94efd-091c-4072-b0e0-406dbe0505ae

"""
Alignment verification workflow check.
Refactored to be circular-safe.

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
        if not file_path:
            return []

        # DEFERRED IMPORT: Break circular dependency on Registry
        from mind.governance.audit_context import AuditorContext
        from mind.governance.filtered_audit import run_filtered_audit

        violations = []
        auditor_ctx = AuditorContext(self._paths.repo_root)

        # Check current compliance
        findings, _, _ = await run_filtered_audit(auditor_ctx, rule_patterns=[r".*"])
        file_violations = [f for f in findings if f.get("file_path") == str(file_path)]

        if file_violations:
            violations.append(f"File has {len(file_violations)} outstanding violations")

        # CONSTITUTIONAL FIX: Use service_registry.session() instead of get_session()
        from body.services.service_registry import service_registry

        async with service_registry.session() as session:
            result = await session.execute(
                text(
                    "SELECT ok FROM core.action_results WHERE action_type = 'alignment' AND file_path = :p ORDER BY created_at DESC LIMIT 1"
                ),
                {"p": str(file_path)},
            )
            row = result.fetchone()
            if row and not row[0]:
                violations.append("Last alignment attempt failed.")

        return violations
