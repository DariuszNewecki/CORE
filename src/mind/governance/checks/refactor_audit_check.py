# src/mind/governance/checks/refactor_audit_check.py
"""
Enforces refactor.audit_after: Verifies that an audit is running against modified files.
Acts as a 'Compliance Signature' for the audit trail.

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.models import AuditFinding, AuditSeverity


# ID: refactor-audit-enforcement
# ID: a2b3c4d5-e6f7-4a3b-9c8d-7e6f5a4b3c2d
class RefactorAuditEnforcement(EnforcementMethod):
    """Records that refactored files are being audited."""

    # ID: 446e3b53-a1e6-4f11-ab6f-7f962247d63e
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        git_modified_files = getattr(context, "git_modified_files", [])

        if not git_modified_files:
            return []

        src_changes = [
            f for f in git_modified_files if f.startswith("src/") and f.endswith(".py")
        ]

        if not src_changes:
            return findings

        # Generate compliance signature
        file_list_str = "\n".join(f"- {f}" for f in src_changes[:5])
        if len(src_changes) > 5:
            file_list_str += f"\n...and {len(src_changes) - 5} more."

        findings.append(
            self._create_finding(
                message=(
                    f"Refactor Detected. This audit run validates the following changes:\n"
                    f"{file_list_str}"
                ),
                file_path="src/",
            )
        )

        return findings


# ID: a1b2c3d4-e5f6-4a3b-9c8d-7e6f5a4b3c2d
class RefactorAuditCheck(RuleEnforcementCheck):
    """
    Enforces refactor.audit_after.
    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["refactor.audit_after"]

    policy_file: ClassVar = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        RefactorAuditEnforcement(
            rule_id="refactor.audit_after", severity=AuditSeverity.INFO
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
