# src/mind/governance/checks/no_write_intent_check.py
"""
Enforces agent.compliance.no_write_intent: AI agents must not write to disk without consent.
"""

from __future__ import annotations

import ast
from pathlib import Path

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e
class NoWriteIntentCheck(BaseCheck):
    policy_rule_ids = ["agent.compliance.no_write_intent"]

    # ID: 83b325f8-2a02-41ea-85ab-12f9c34b2c73
    def execute(self) -> list[AuditFinding]:
        findings = []

        # Look for any Path(...).write_text() or open(..., "w")
        dangerous_patterns = [
            ("Path", "write_text"),
            ("Path", "write_bytes"),
            ("open", None),  # open(..., "w")
        ]

        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    # Path(...).write_text()
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Attribute):
                            if node.func.attr in ("write_text", "write_bytes"):
                                if (
                                    isinstance(node.func.value, ast.Name)
                                    and node.func.value.id == "Path"
                                ):
                                    findings.append(
                                        self._finding(file_path, node.lineno)
                                    )
                        # open(..., "w")
                        elif isinstance(node.func, ast.Name) and node.func.id == "open":
                            if node.keywords:
                                mode = next(
                                    (
                                        k.value.s
                                        for k in node.keywords
                                        if k.arg == "mode"
                                    ),
                                    None,
                                )
                                if mode and "w" in mode:
                                    findings.append(
                                        self._finding(file_path, node.lineno)
                                    )
            except Exception:
                pass

        return findings

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="agent.compliance.no_write_intent",
            severity=AuditSeverity.ERROR,
            message="AI agent attempted disk write without consent.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
