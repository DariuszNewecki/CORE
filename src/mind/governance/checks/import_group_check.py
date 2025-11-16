# src/mind/governance/checks/import_group_check.py
"""
Enforces layout.import_grouping: Imports must be grouped: stdlib → third-party → local.
"""

from __future__ import annotations

import ast
import re
from pathlib import Path

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck  # ← FIXED


# ID: q7r8s9t0-u1v2-2w3x-4y5z-6a7b8c9d0e1f
# ID: 18776480-eaa4-4d61-b6dc-4f17059f7777
class ImportGroupCheck(BaseCheck):
    policy_rule_ids = ["layout.import_grouping"]

    _GROUP_ORDER = [
        r"^import [a-zA-Z0-9_]+$",  # stdlib: import os
        r"^from [a-zA-Z0-9_]+ import",  # stdlib: from pathlib import Path
        r"^import [a-zA-Z0-9_.-]+$",  # third-party: import requests
        r"^from [a-zA-Z0-9_.-]+ import",  # third-party: from fastapi import FastAPI
        r"^import \.",  # local: import .utils
        r"^from \. import",  # local: from . import models
        r"^from \.\. import",  # local: from .. import services
    ]

    # ID: 5eb90564-22d8-4cb1-b208-086a6eaa143d
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        for file_path in self.context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                import_nodes = [
                    node
                    for node in ast.walk(tree)
                    if isinstance(node, (ast.Import, ast.ImportFrom))
                ]

                if not import_nodes:
                    continue

                # Extract import lines
                lines = content.splitlines()
                import_lines = []
                for node in import_nodes:
                    line_no = node.lineno - 1
                    line = lines[line_no].strip()
                    if line.startswith(("import ", "from ")):
                        import_lines.append((line_no, line))

                # Check grouping order
                prev_group = -1
                for line_no, line in import_lines:
                    matched = False
                    for group_idx, pattern in enumerate(self._GROUP_ORDER):
                        if re.match(pattern, line):
                            if group_idx < prev_group:
                                findings.append(self._finding(file_path, line_no + 1))
                            prev_group = group_idx
                            matched = True
                            break
                    if not matched:
                        findings.append(self._finding(file_path, line_no + 1))

            except Exception as e:
                findings.append(
                    AuditFinding(
                        check_id="layout.import_grouping",
                        severity=AuditSeverity.WARN,
                        message=f"Parse error: {e}",
                        file_path=str(file_path.relative_to(self.repo_root)),
                        line_number=1,
                    )
                )

        return findings

    def _finding(self, file_path: Path, line: int) -> AuditFinding:
        return AuditFinding(
            check_id="layout.import_grouping",
            severity=AuditSeverity.WARN,
            message="Imports not properly grouped. Run `fix import-group`.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=line,
        )
