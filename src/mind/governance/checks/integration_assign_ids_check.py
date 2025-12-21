# src/mind/governance/checks/integration_assign_ids_check.py
"""
Enforces integration.assign_ids_required: All public symbols must have stable UUIDs.

Verifies:
- integration.assign_ids_required - Stable UUIDs must be assigned to all new public symbols

Ref: .intent/charter/standards/operations/operations.json
"""

from __future__ import annotations

import ast
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: assign-ids-enforcement
# ID: d1e2f3a4-b5c6-7d8e-9f0a-1b2c3d4e5f6a
class AssignIdsEnforcement(EnforcementMethod):
    """
    Scans Python files for public symbols (functions, classes, methods)
    that lack '# ID:' tags.

    Public symbols are those that don't start with underscore. Private helpers
    (starting with '_') are exempt as they're implementation details.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: a9b8c7d6-e5f4-3a2b-1c0d-9e8f7a6b5c4d
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        for file_path in context.python_files:
            # Skip test files - they don't need IDs
            rel_path = str(file_path.relative_to(context.repo_path))
            if "test" in rel_path or rel_path.startswith("tests/"):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    # Check functions, async functions, and classes
                    if not isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        continue

                    symbol_name = getattr(node, "name", "")

                    # Skip private symbols (they don't need IDs)
                    if symbol_name.startswith("_"):
                        continue

                    # Check if there's an ID comment above this symbol
                    lineno = getattr(node, "lineno", 0)
                    if lineno < 2:
                        # Can't have an ID comment if it's on line 1
                        findings.append(
                            self._create_finding(
                                message=f"Public symbol '{symbol_name}' missing '# ID:' tag. Run 'core-admin fix ids --write' to assign.",
                                file_path=rel_path,
                                line_number=lineno,
                            )
                        )
                        continue

                    # Look at the lines above the symbol
                    has_id = False
                    for check_line_idx in range(max(0, lineno - 3), lineno - 1):
                        if check_line_idx < len(lines):
                            line = lines[check_line_idx].strip()
                            if line.startswith("# ID:") or line.startswith("#ID:"):
                                has_id = True
                                break

                    if not has_id:
                        findings.append(
                            self._create_finding(
                                message=f"Public symbol '{symbol_name}' missing '# ID:' tag. Run 'core-admin fix ids --write' to assign.",
                                file_path=rel_path,
                                line_number=lineno,
                            )
                        )

            except Exception as e:
                logger.debug("Failed to scan %s for missing IDs: %s", file_path, e)
                continue

        if findings:
            logger.warning(
                "Found %d public symbol(s) without IDs. Integration blocked.",
                len(findings),
            )

        return findings


# ID: e2f3a4b5-c6d7-8e9f-0a1b-2c3d4e5f6a7b
class IntegrationAssignIdsCheck(RuleEnforcementCheck):
    """
    Enforces integration.assign_ids_required before integration.

    Ref: .intent/charter/standards/operations/operations.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["integration.assign_ids_required"]

    policy_file: ClassVar = settings.paths.policy("operations")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        AssignIdsEnforcement(
            rule_id="integration.assign_ids_required",
            severity=AuditSeverity.ERROR,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
