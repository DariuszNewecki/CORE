# src/mind/governance/checks/private_id_check.py
"""
Enforces symbols.private_helpers_no_id_required: Private helpers MUST NOT have CAPABILITY_ID.
"""

from __future__ import annotations

import ast
from pathlib import Path

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: n4o5p6q7-r8s9-9t0u-1v2w-3x4y5z6a7b8c
# ID: 0b282023-fc61-4fa1-9118-1220a87ce07f
class PrivateIdCheck(BaseCheck):
    policy_rule_ids = ["symbols.private_helpers_no_id_required"]

    # ID: 0d5f4f67-8c0c-40f7-aa2f-edcee08a1b71
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        for file_path in self.context.python_files:
            if not file_path.name.startswith("_"):
                continue  # Only private files

            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                has_cap_id = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id == "CAPABILITY_ID"
                            ):
                                has_cap_id = True
                                line_no = node.lineno
                                break
                        if has_cap_id:
                            break

                if has_cap_id:
                    findings.append(self._finding(file_path, line_no))

            except Exception as e:
                findings.append(
                    AuditFinding(
                        check_id="symbols.private_helpers_no_id_required",
                        severity=AuditSeverity.WARN,
                        message=f"Parse error in {file_path.name}: {e}",
                        file_path=str(file_path.relative_to(self.repo_root)),
                        line_number=1,
                    )
                )

        return findings

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="symbols.private_helpers_no_id_required",
            severity=AuditSeverity.WARN,
            message="Private helper contains CAPABILITY_ID. Remove it.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
