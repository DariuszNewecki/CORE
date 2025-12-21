# src/mind/governance/checks/cli_naming_check.py
"""
Enforces symbols.cli_async_helpers_private: CLI async helpers must be private (_name).

Ref: .intent/charter/standards/code_standards.json
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
from shared.models import AuditFinding, AuditSeverity


# ID: cli-naming-enforcement
# ID: e9f0a1b2-c3d4-5e6f-7a8b-9c0d1e2f3a4b
class CliNamingEnforcement(EnforcementMethod):
    """Verifies that async helper functions in CLI are private."""

    # ID: b9616e24-b8a6-4824-ba22-61b5f7cb519e
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        cli_dir = context.repo_path / "src" / "body" / "cli"
        if not cli_dir.exists():
            return findings

        for file_path in cli_dir.rglob("*.py"):
            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if isinstance(node, ast.AsyncFunctionDef):
                        # If it's an async function and doesn't start with _
                        if not node.name.startswith("_"):
                            # Check if it's a helper (not a Click command)
                            has_click_decorator = any(
                                (isinstance(dec, ast.Name) and dec.id == "command")
                                or (
                                    isinstance(dec, ast.Attribute)
                                    and dec.attr in ["command", "group"]
                                )
                                for dec in node.decorator_list
                            )

                            if not has_click_decorator:
                                findings.append(
                                    self._create_finding(
                                        message=f"Async helper '{node.name}' in CLI must be private (start with _)",
                                        file_path=str(
                                            file_path.relative_to(context.repo_path)
                                        ),
                                        line_number=node.lineno,
                                    )
                                )

            except Exception:
                pass

        return findings


# ID: f0a1b2c3-d4e5-6f7a-8b9c-0d1e2f3a4b5c
class CliNamingCheck(RuleEnforcementCheck):
    """
    Enforces symbols.cli_async_helpers_private.
    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["symbols.cli_async_helpers_private"]

    policy_file: ClassVar = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        CliNamingEnforcement(
            rule_id="symbols.cli_async_helpers_private", severity=AuditSeverity.WARNING
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
