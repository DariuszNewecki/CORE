# src/mind/governance/checks/capability_owner_check.py
"""
Enforces Purity: Ensures no legacy '# owner:' tags remain in source code.
Ownership MUST be defined in the Database (SSOT), not in files.

Ref: .intent/charter/standards/code/purity.json
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


# ID: no-descriptive-pollution-enforcement
# ID: 57976a20-6b66-436b-95a0-1bbba3da0f56
class NoDescriptivePollutionEnforcement(EnforcementMethod):
    """
    Scans for legacy '# owner:' tags and flags them as Constitutional Violations.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 86210c03-32c1-4685-976b-2376650ce633
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # Scan all python files in src
        for file_path in context.src_dir.rglob("*.py"):
            try:
                lines = file_path.read_text(encoding="utf-8").splitlines()
                for i, line in enumerate(lines, 1):
                    if line.strip().startswith("# owner:"):
                        findings.append(
                            self._create_finding(
                                message=(
                                    "Forbidden Pollution: '# owner:' tag found. "
                                    "Ownership must be managed via the Database/Manifest, "
                                    "not source comments."
                                ),
                                file_path=str(file_path.relative_to(context.repo_path)),
                                line_number=i,
                            )
                        )
            except Exception:
                # If file can't be read, other checks will catch it
                continue

        return findings


# ID: 40d50b0f-01cd-43d7-a41a-baf24f153852
class CapabilityOwnerCheck(RuleEnforcementCheck):
    """
    Scans for legacy '# owner:' tags and flags them as Constitutional Violations.

    Ref: .intent/charter/standards/code/purity.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "purity.no_descriptive_pollution",
    ]

    policy_file: ClassVar = settings.paths.policy("purity")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        NoDescriptivePollutionEnforcement(rule_id="purity.no_descriptive_pollution"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
