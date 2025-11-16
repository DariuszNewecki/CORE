# src/mind/governance/checks/runtime_validation_check.py
"""
Enforces agent.execution.require_runtime_validation: Code must be validated before execution.
"""

from __future__ import annotations

import ast
from pathlib import Path

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: f6a7b8c9-d0e1-4f2a-3b4c-5d6e7f8a9b0c
class RuntimeValidationCheck(BaseCheck):
    policy_rule_ids = ["agent.execution.require_runtime_validation"]

    # ID: f447aaef-aa90-4c4e-9fd6-7415ad583816
    def execute(self) -> list[AuditFinding]:
        findings = []

        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue

                    # Look for exec/eval without prior validation
                    if isinstance(node.func, ast.Name) and node.func.id in (
                        "exec",
                        "eval",
                    ):
                        # Check if previous line has validation
                        prev_line = (
                            content.splitlines()[node.lineno - 2]
                            if node.lineno > 1
                            else ""
                        )
                        if (
                            "validate_code" not in prev_line
                            and "verified_code" not in prev_line
                        ):
                            findings.append(self._finding(file_path, node.lineno))
            except Exception:
                pass

        return findings

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="agent.execution.require_runtime_validation",
            severity=AuditSeverity.ERROR,
            message="Code executed without runtime validation. Use `fix validate-runtime`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
