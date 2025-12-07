# src/mind/governance/checks/trace_check.py
"""
Enforces agent.reasoning.trace_required: Every reason(...) call must be followed by TRACE: log.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 599dcb6a-e809-498c-a319-67121529b34c
class ReasoningTraceCheck(BaseCheck):
    policy_rule_ids = ["agent.reasoning.trace_required"]

    # ID: 747497cc-32bd-4f92-9a64-0c94b2b0a0c8
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))
                lines = content.splitlines()

                reason_calls = []
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        if isinstance(node.func, ast.Name) and node.func.id == "reason":
                            reason_calls.append(node.lineno)

                # Look for TRACE: in next 3 lines after reason()
                for lineno in reason_calls:
                    found_trace = False
                    for offset in range(1, 4):
                        check_line = lineno + offset - 1
                        if check_line < len(lines) and "TRACE:" in lines[check_line]:
                            found_trace = True
                            break
                    if not found_trace:
                        findings.append(self._finding(file_path, lineno))

            except Exception as e:
                findings.append(
                    AuditFinding(
                        check_id="agent.reasoning.trace_required",
                        severity=AuditSeverity.WARNING,
                        message=f"Parse error in {file_path.name}: {e}",
                        file_path=str(file_path.relative_to(self.repo_root)),
                        line_number=1,
                    )
                )

        return findings

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="agent.reasoning.trace_required",
            severity=AuditSeverity.WARNING,
            message="reason() called without TRACE: log. Add `logger.info('TRACE: ...')`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
