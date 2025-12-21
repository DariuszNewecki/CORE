# src/mind/governance/checks/update_caps_check.py
"""
Enforces refactor.update_capabilities: All capability modules must define CAPABILITY_ID.

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.models import AuditFinding, AuditSeverity


# ID: update-caps-enforcement
# ID: 8b9c0d1e-2f3a-4b5c-6d7e-8f9a0b1c2d3e
class UpdateCapsEnforcement(EnforcementMethod):
    """Verifies that capability modules define CAPABILITY_ID."""

    # ID: a192afaf-bec3-48e2-bef8-5f8c149d86f9
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []
        caps_dir = Path("src/capabilities")

        if not caps_dir.exists():
            return findings

        for cap_file in caps_dir.glob("*.py"):
            if cap_file.name.startswith("_"):
                continue

            try:
                content = cap_file.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(cap_file))

                has_cap_id = False
                for node in ast.walk(tree):
                    if isinstance(node, ast.Assign):
                        for target in node.targets:
                            if (
                                isinstance(target, ast.Name)
                                and target.id == "CAPABILITY_ID"
                            ):
                                has_cap_id = True
                                break
                        if has_cap_id:
                            break

                if not has_cap_id:
                    findings.append(
                        self._create_finding(
                            message="Capability module missing CAPABILITY_ID. Run `fix update-caps`.",
                            file_path=str(cap_file.relative_to(context.repo_path)),
                            line_number=1,
                        )
                    )

            except Exception as e:
                findings.append(
                    self._create_finding(
                        message=f"Failed to parse {cap_file}: {e}",
                        file_path=str(cap_file.relative_to(context.repo_path)),
                        line_number=1,
                    )
                )

        return findings


# ID: 624c92aa-575c-406f-ac4b-58f5d87558f1
class UpdateCapsCheck(RuleEnforcementCheck):
    """
    Enforces refactor.update_capabilities.
    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["refactor.update_capabilities"]

    policy_file: ClassVar = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        UpdateCapsEnforcement(
            rule_id="refactor.update_capabilities", severity=AuditSeverity.WARNING
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
