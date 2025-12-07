# src/mind/governance/checks/governed_db_write_check.py
"""
Enforces db.write_via_governed_cli: All DB writes must use core-admin db write.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: dca11664-1e80-4fc9-84e0-41e169f5a6ae
class GovernedDbWriteCheck(BaseCheck):
    policy_rule_ids = ["db.write_via_governed_cli"]

    # ID: 4d237ba8-c2ad-432f-ba7e-6c7e3df7a29e
    def execute(self) -> list[AuditFinding]:
        findings = []

        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if not isinstance(node, ast.Call):
                        continue

                    # Look for session.add(), session.commit(), etc.
                    if isinstance(node.func, ast.Attribute):
                        attr = node.func.attr
                        obj = node.func.value
                        if attr in (
                            "add",
                            "add_all",
                            "delete",
                            "merge",
                            "commit",
                            "flush",
                        ):
                            if isinstance(obj, ast.Attribute) and obj.attr == "session":
                                # Allow if in core-admin db write
                                if "db write" in content or "fix db-write" in content:
                                    continue
                                findings.append(self._finding(file_path, node.lineno))
            except Exception:
                pass

        return findings

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="db.write_via_governed_cli",
            severity=AuditSeverity.ERROR,
            message="Direct DB write detected. Use `core-admin db write`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
