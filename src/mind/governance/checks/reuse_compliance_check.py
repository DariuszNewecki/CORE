# src/mind/governance/checks/reuse_compliance_check.py
"""
Enforces reuse.before_new_code: Verifies that the Reuse Infrastructure exists.
This is a prerequisite check; Agents cannot comply if the tool is missing.
"""

from __future__ import annotations

import ast
from typing import ClassVar

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 8df4517a-dcaa-41da-ab50-79539ad496bf
class ReuseComplianceCheck(BaseCheck):
    """
    Verifies that the code reuse infrastructure (ReuseFinder) is implemented
    and available to agents.
    Ref: standard_code_general (reuse.before_new_code)
    """

    policy_rule_ids: ClassVar[list[str]] = ["reuse.before_new_code"]

    # ID: a3de7c56-6470-4cf4-a845-2315d32547ee
    def execute(self) -> list[AuditFinding]:
        findings = []

        # Canonical location for Reuse Logic
        reuse_module_path = self.src_dir / "shared/infrastructure/context/reuse.py"

        if not reuse_module_path.exists():
            findings.append(
                AuditFinding(
                    check_id="reuse.before_new_code",
                    severity=AuditSeverity.ERROR,
                    message=(
                        "Reuse infrastructure is missing. Agents cannot comply with reuse policy. "
                        "Expected: 'src/shared/infrastructure/context/reuse.py'"
                    ),
                    file_path="src/shared/infrastructure/context/reuse.py",
                )
            )
            return findings

        try:
            content = reuse_module_path.read_text(encoding="utf-8")
            tree = ast.parse(content)

            # Verify the class exists
            has_reuse_finder = any(
                isinstance(node, ast.ClassDef) and node.name == "ReuseFinder"
                for node in ast.walk(tree)
            )

            if not has_reuse_finder:
                findings.append(
                    AuditFinding(
                        check_id="reuse.before_new_code",
                        severity=AuditSeverity.ERROR,
                        message="ReuseFinder class missing in reuse infrastructure module.",
                        file_path=str(reuse_module_path.relative_to(self.repo_root)),
                    )
                )

        except SyntaxError:
            findings.append(
                AuditFinding(
                    check_id="reuse.before_new_code",
                    severity=AuditSeverity.ERROR,
                    message="Syntax error in reuse infrastructure module.",
                    file_path=str(reuse_module_path.relative_to(self.repo_root)),
                )
            )
        except Exception as e:
            logger.error("Failed to parse reuse module: %s", e, exc_info=True)
            findings.append(
                AuditFinding(
                    check_id="reuse.before_new_code",
                    severity=AuditSeverity.ERROR,
                    message=f"Internal error verifying reuse infrastructure: {e}",
                    file_path=str(reuse_module_path.relative_to(self.repo_root)),
                )
            )

        return findings
