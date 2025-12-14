# src/mind/governance/checks/private_id_check.py
"""
Enforces symbols.private_helpers_no_id_required.
Private symbols (starting with '_') are implementation details and MUST NOT
have Capability IDs, as they are not managed capabilities.
"""

from __future__ import annotations

import ast

from mind.governance.checks.base_check import BaseCheck
from shared.ast_utility import find_symbol_id_and_def_line
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 0b282023-fc61-4fa1-9118-1220a87ce07f
class PrivateIdCheck(BaseCheck):
    """
    Scans for private symbols ('_function', '_Class') that strictly have
    an assigned '# ID:' tag. This is forbidden as private helpers should
    remain ungoverned implementation details.
    Ref: standard_code_general (symbols.private_helpers_no_id_required)
    """

    policy_rule_ids = ["symbols.private_helpers_no_id_required"]

    # ID: 0d5f4f67-8c0c-40f7-aa2f-edcee08a1b71
    def execute(self) -> list[AuditFinding]:
        findings = []

        for file_path in self.src_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                source_lines = content.splitlines()
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if not isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        continue

                    # We only care about Private symbols
                    if not node.name.startswith("_"):
                        continue

                    # Skip magic methods (__init__) as they are structural, not helpers
                    if node.name.startswith("__") and node.name.endswith("__"):
                        continue

                    # Check if it has an ID tag
                    id_result = find_symbol_id_and_def_line(node, source_lines)

                    if id_result.has_id:
                        findings.append(
                            AuditFinding(
                                check_id="symbols.private_helpers_no_id_required",
                                severity=AuditSeverity.WARNING,  # Per policy
                                message=(
                                    f"Private symbol '{node.name}' has a Capability ID. "
                                    "Private helpers must be ungoverned implementation details. Remove the '# ID:' tag."
                                ),
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=id_result.definition_line_num,
                            )
                        )

            except Exception as e:
                logger.debug("Failed to check private IDs in %s: %s", file_path, e)

        return findings
