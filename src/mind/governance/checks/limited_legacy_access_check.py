# src/mind/governance/checks/limited_legacy_access_check.py
"""
Enforces knowledge.limited_legacy_access: No direct access to legacy systems.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: k1l2m3n4-o5p6-6q7r-8s9t-0u1v2w3x4y5z
# ID: 1572122b-d11a-4ed4-89d7-678b92779480
class LimitedLegacyAccessCheck(BaseCheck):
    policy_rule_ids = ["knowledge.limited_legacy_access"]

    # ID: 90fab030-8d3e-443a-9d8e-93abae8fc2e2
    def execute(self) -> list[AuditFinding]:
        findings = []
        legacy_paths = ["legacy/", "old_system/", "deprecated/"]

        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if isinstance(node, ast.ImportFrom):
                        if node.module and any(
                            legacy in node.module for legacy in legacy_paths
                        ):
                            findings.append(self._finding(file_path, node.lineno))
                    elif isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            if "legacy" in node.func.attr.lower():
                                findings.append(self._finding(file_path, node.lineno))
            except Exception:
                pass

        return findings

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="knowledge.limited_legacy_access",
            severity=AuditSeverity.ERROR,
            message="Direct access to legacy system. Use `fix legacy-access`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
