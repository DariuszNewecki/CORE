# src/mind/governance/checks/reuse_compliance_check.py
"""
Enforces reuse.before_new_code: Verifies that reuse infrastructure exists.
"""

from __future__ import annotations

import ast

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 8df4517a-dcaa-41da-ab50-79539ad496bf
class ReuseComplianceCheck(BaseCheck):
    """
    Verifies that the code reuse infrastructure (ReuseFinder) is implemented
    and available to agents, ensuring compliance with 'reuse.before_new_code'.
    """

    policy_rule_ids = ["reuse.before_new_code"]

    # ID: a3de7c56-6470-4cf4-a845-2315d32547ee
    def execute(self) -> list[AuditFinding]:
        findings = []
        reuse_module_path = (
            self.repo_root / "src/shared/infrastructure/context/reuse.py"
        )

        if not reuse_module_path.exists():
            findings.append(
                AuditFinding(
                    check_id="reuse.before_new_code",
                    severity=AuditSeverity.ERROR,
                    message="Reuse infrastructure missing. 'src/shared/infrastructure/context/reuse.py' not found.",
                    file_path="src/shared/infrastructure/context/reuse.py",
                )
            )
            return findings

        try:
            content = reuse_module_path.read_text(encoding="utf-8")
            tree = ast.parse(content)
            has_reuse_finder = any(
                isinstance(node, ast.ClassDef) and node.name == "ReuseFinder"
                for node in ast.walk(tree)
            )

            if not has_reuse_finder:
                findings.append(
                    AuditFinding(
                        check_id="reuse.before_new_code",
                        severity=AuditSeverity.ERROR,
                        message="ReuseFinder class missing in 'src/shared/infrastructure/context/reuse.py'.",
                        file_path="src/shared/infrastructure/context/reuse.py",
                    )
                )
        except Exception as e:
            findings.append(
                AuditFinding(
                    check_id="reuse.before_new_code",
                    severity=AuditSeverity.ERROR,
                    message=f"Failed to parse reuse module: {e}",
                    file_path="src/shared/infrastructure/context/reuse.py",
                )
            )

        return findings
