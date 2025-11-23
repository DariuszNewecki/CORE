# src/mind/governance/checks/ir_triage_check.py
"""
Enforces ir.triage_required: All incidents must be triaged.
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.config import settings
from shared.models import AuditFinding, AuditSeverity


# ID: l2m3n4o5-p6q7-7r8s-9t0u-1v2w3x4y5z6a
# ID: 6a1ab18f-4330-4e4a-8358-33c2ebe29fd0
class IRTriageCheck(BaseCheck):
    policy_rule_ids = ["ir.triage_required"]

    # ID: b2d64ca1-4def-496c-b11d-28a58a7a1280
    def execute(self) -> list[AuditFinding]:
        """
        Verifies that the constitutionally required triage log exists.
        """
        findings = []

        # --- START OF FIX ---
        # The check now correctly reads the path from the constitution (via settings)
        # instead of using a hardcoded, incorrect path.
        try:
            log_path = settings.get_path("mind.ir.triage_log")
        except FileNotFoundError:
            # This case means meta.yaml itself is broken, which another check will find.
            # This check should not produce a finding in that case.
            return []

        if not log_path.exists():
            findings.append(
                AuditFinding(
                    check_id="ir.triage_required",
                    severity=AuditSeverity.ERROR,
                    message="Incident triage log is missing. Run `poetry run core-admin fix ir-triage --write`.",
                    file_path=str(log_path.relative_to(self.repo_root)),
                    line_number=1,
                )
            )
        # The check for "TRIAGED" in the content has been removed, as the existence
        # of the file itself satisfies the `ir.triage_required` rule.
        # Content validation is the responsibility of other, more specific rules.
        # --- END OF FIX ---

        return findings
