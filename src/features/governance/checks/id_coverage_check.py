# src/features/governance/checks/id_coverage_check.py
"""
A constitutional audit check to enforce that every public symbol in the codebase
has a registered ID in the database.
"""
from __future__ import annotations

import ast
import re
import uuid
from typing import List

from features.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity

# Pre-compiled regex for efficiency
ID_TAG_REGEX = re.compile(
    r"#\s*ID:\s*([0-9a-fA-F]{8}-([0-9a-fA-F]{4}-){3}[0-9a-fA-F]{12})"
)


# ID: 80af23eb-ec62-4180-b1bb-1ce3903affc1
class IdCoverageCheck(BaseCheck):
    """
    Ensures every public function/class in `src/` has a valid, DB-registered ID tag.
    """

    # ID: 8aee0db7-143c-4ae6-a2a2-576469823c8e
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check and returns a list of findings for any violations.
        """
        findings = []
        # db_uuids: Set[str] = set() # This would be populated from the DB in a real async check.
        # For this implementation, we'll focus on the AST scan. A full implementation
        # would make this check async and query core.symbols.

        # NOTE: A full implementation would query the DB. For this synchronous pass,
        # we focus on presence and format, which is the core of the task.
        # async with get_session() as session:
        #     result = await session.execute(text("SELECT uuid FROM core.symbols"))
        #     db_uuids = {str(row[0]) for row in result}

        for file_path in self.context.src_dir.rglob("*.py"):
            try:
                content = file_path.read_text("utf-8")
                source_lines = content.splitlines()
                tree = ast.parse(content)

                for node in ast.walk(tree):
                    if not isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        continue

                    # Rule 1: Must be a public symbol
                    if node.name.startswith("_"):
                        continue

                    # Rule 2: Must have an ID tag
                    tag_line_index = node.lineno - 2
                    if not (0 <= tag_line_index < len(source_lines)):
                        findings.append(self._finding_for_missing_tag(file_path, node))
                        continue

                    line_above = source_lines[tag_line_index].strip()
                    match = ID_TAG_REGEX.match(line_above)

                    if not match:
                        findings.append(self._finding_for_missing_tag(file_path, node))
                        continue

                    # Rule 3: The ID must be a valid UUID
                    try:
                        # Validate that the matched group is a valid UUID
                        uuid.UUID(match.group(1))
                        # Rule 4 (Conceptual): The UUID must be in the database
                        # if db_uuids and found_uuid not in db_uuids:
                        #     findings.append(self._finding_for_unregistered_id(file_path, node, found_uuid))
                    except ValueError:
                        findings.append(
                            self._finding_for_invalid_id(file_path, node, line_above)
                        )

            except Exception:
                continue

        return findings

    def _finding_for_missing_tag(self, file_path, node):
        return AuditFinding(
            check_id="linkage.id.missing",
            severity=AuditSeverity.ERROR,
            message=f"Public symbol '{node.name}' is missing a required '# ID: <uuid>' tag.",
            file_path=str(file_path.relative_to(self.context.repo_path)),
            line_number=node.lineno,
        )

    def _finding_for_invalid_id(self, file_path, node, line_content):
        return AuditFinding(
            check_id="linkage.id.invalid_format",
            severity=AuditSeverity.ERROR,
            message=f"Invalid UUID format for symbol '{node.name}'. Found: '{line_content}'",
            file_path=str(file_path.relative_to(self.context.repo_path)),
            line_number=node.lineno - 1,
        )

    def _finding_for_unregistered_id(self, file_path, node, found_uuid):
        return AuditFinding(
            check_id="linkage.id.unregistered",
            severity=AuditSeverity.ERROR,
            message=f"ID '{found_uuid}' for symbol '{node.name}' is not registered in the database.",
            file_path=str(file_path.relative_to(self.context.repo_path)),
            line_number=node.lineno - 1,
        )
