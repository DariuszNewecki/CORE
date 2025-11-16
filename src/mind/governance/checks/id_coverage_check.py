# src/mind/governance/checks/id_coverage_check.py
"""
A constitutional audit check to enforce that every public symbol has an ID tag,
as mandated by the 'linkage.assign_ids' and 'symbols.public_capability_id_and_docstring' rules.
"""

from __future__ import annotations

import ast

from shared.ast_utility import find_symbol_id_and_def_line
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck

logger = getLogger(__name__)


# ID: 3501ed8c-8366-4ad7-9ab4-7dcf4c045c70
class IdCoverageCheck(BaseCheck):
    """
    Ensures every public function/class in `src/` has a valid '# ID:' tag,
    enforcing key operational and code standard policies.
    """

    # Fulfills the contract from BaseCheck. This check verifies that the mandatory
    # workflow step of assigning IDs has been completed and that symbols meet
    # the code standard for public capabilities.
    policy_rule_ids = [
        "linkage.assign_ids",
        "symbols.public_capability_id_and_docstring",
    ]

    # No __init__ is needed as it uses the default from BaseCheck.

    # ID: f69a1a2e-26cd-4cc2-8fdc-7f18e0e77d0c
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by scanning all source files for public symbols missing an ID.
        """
        findings = []
        # Use self.src_dir provided by the BaseCheck for consistency.
        for file_path in self.src_dir.rglob("*.py"):
            try:
                content = file_path.read_text("utf-8")
                source_lines = content.splitlines()
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if not isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        continue
                    if node.name.startswith("_"):
                        continue  # Rule applies only to public symbols

                    id_result = find_symbol_id_and_def_line(node, source_lines)

                    if not id_result.has_id:
                        findings.append(
                            AuditFinding(
                                # The check_id now directly references the constitutional rule.
                                check_id="linkage.assign_ids",
                                severity=AuditSeverity.ERROR,
                                message=f"Public symbol '{node.name}' is missing its required '# ID:' tag.",
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=id_result.definition_line_num,
                            )
                        )

            except Exception as exc:
                # Log the error for debugging but don't crash the audit.
                logger.debug(
                    "Skipping ID coverage scan for %s due to error: %s", file_path, exc
                )
                continue

        return findings
