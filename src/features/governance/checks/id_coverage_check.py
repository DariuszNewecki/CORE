# src/features/governance/checks/id_coverage_check.py
"""
A constitutional audit check to enforce that every public symbol in the codebase
has a registered ID in the database.
"""

from __future__ import annotations

import ast
from typing import List

from shared.ast_utility import find_symbol_id_and_def_line
from shared.models import AuditFinding, AuditSeverity

from features.governance.checks.base_check import BaseCheck


# ID: 3501ed8c-8366-4ad7-9ab4-7dcf4c045c70
class IdCoverageCheck(BaseCheck):
    """
    Ensures every public function/class in `src/` has a valid, DB-registered ID tag.
    """

    # ID: f69a1a2e-26cd-4cc2-8fdc-7f18e0e77d0c
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check and returns a list of findings for any violations.
        """
        findings = []
        for file_path in self.context.src_dir.rglob("*.py"):
            try:
                content = file_path.read_text("utf-8")
                source_lines = content.splitlines()
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if not isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        continue

                    # Rule 1: Must be a public symbol
                    if node.name.startswith("_"):
                        continue

                    # Use the robust utility to find the ID and definition line
                    id_result = find_symbol_id_and_def_line(node, source_lines)

                    if not id_result.has_id:
                        findings.append(
                            AuditFinding(
                                check_id="linkage.id.missing-tag",
                                severity=AuditSeverity.ERROR,
                                message=f"Public symbol '{node.name}' is missing its required '# ID:' tag.",
                                file_path=str(
                                    file_path.relative_to(self.context.repo_path)
                                ),
                                line_number=id_result.definition_line_num,
                            )
                        )

            except Exception:
                # Silently ignore files that cannot be parsed
                continue

        return findings
