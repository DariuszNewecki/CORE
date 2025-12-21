# src/mind/governance/checks/private_id_check.py
"""
Enforces symbols.private_helpers_no_id_required: Private helpers must not have ID tags.

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

import ast
import re
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.models import AuditFinding, AuditSeverity


ID_TAG_REGEX = re.compile(r"#\s*ID:\s*([a-zA-Z0-9_-]+)")


# ID: private-id-enforcement
# ID: 9c0d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class PrivateIdEnforcement(EnforcementMethod):
    """Verifies that private helpers do not have ID tags."""

    # ID: 33914189-4548-42ee-98ce-2adb8ab333fa
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        for file_path in context.python_files:
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in tree.body:
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("_"):
                        # Check if there's an ID tag above this function
                        start_line = max(1, node.lineno - 3)
                        lines = content.splitlines()[start_line - 1 : node.lineno]

                        for i, line in enumerate(lines, start=start_line):
                            if ID_TAG_REGEX.search(line):
                                findings.append(
                                    self._create_finding(
                                        message=(
                                            f"Private helper '{node.name}' has an ID tag. "
                                            "Private helpers must be ungoverned implementation details. "
                                            "Remove the '# ID:' tag."
                                        ),
                                        file_path=str(
                                            file_path.relative_to(context.repo_path)
                                        ),
                                        line_number=i,
                                    )
                                )

            except Exception:
                pass  # Skip parse errors

        return findings


# ID: e8f1e7d6-c5b4-4a39-82d1-9e0f8d7c6b5a
class PrivateIdCheck(RuleEnforcementCheck):
    """
    Enforces symbols.private_helpers_no_id_required.
    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["symbols.private_helpers_no_id_required"]

    policy_file: ClassVar = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        PrivateIdEnforcement(
            rule_id="symbols.private_helpers_no_id_required",
            severity=AuditSeverity.WARNING,
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
