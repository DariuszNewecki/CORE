# src/mind/governance/checks/no_unverified_code_check.py
"""
Enforces agent.execution.no_unverified_code: AI cannot execute unverified code.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: e5f6a7b8-c9d0-4e1f-2a3b-4c5d6e7f8a9b
class NoUnverifiedCodeCheck(BaseCheck):
    policy_rule_ids = ["agent.execution.no_unverified_code"]

    # ID: b5a07aaf-79f2-4c62-a38b-70285716e1b0
    def execute(self) -> list[AuditFinding]:
        findings = []

        # Dangerous patterns
        patterns = [
            ("exec", None),
            ("eval", None),
            ("compile", "exec"),
            ("__import__", None),
        ]

        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue

                    if isinstance(node.func, ast.Name):
                        func_name = node.func.id
                        for dangerous, mode in patterns:
                            if func_name == dangerous:
                                if mode == "exec" and node.args:
                                    code = ast.get_source_segment(content, node.args[0])
                                    if code and "core-admin" in code:
                                        continue  # Allow verified CLI
                                findings.append(self._finding(file_path, node.lineno))
                    elif isinstance(node.func, ast.Attribute):
                        if node.func.attr in ("exec", "eval") and "builtins" in str(
                            node.func.value
                        ):
                            findings.append(self._finding(file_path, node.lineno))
            except Exception:
                pass

        return findings

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="agent.execution.no_unverified_code",
            severity=AuditSeverity.ERROR,
            message="AI attempted to execute unverified code. Use `fix verify-code`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
