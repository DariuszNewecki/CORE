# src/mind/governance/checks/ir_triage_check.py
"""
Enforces ir.triage_required: All incidents must be triaged.
"""

from __future__ import annotations

from pathlib import Path

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: l2m3n4o5-p6q7-7r8s-9t0u-1v2w3x4y5z6a
# ID: 6a1ab18f-4330-4e4a-8358-33c2ebe29fd0
class IRTriageCheck(BaseCheck):
    policy_rule_ids = ["ir.triage_required"]

    # ID: b2d64ca1-4def-496c-b11d-28a58a7a1280
    def execute(self) -> list[AuditFinding]:
        findings = []
        log_path = Path(".core/incident.log")

        if not log_path.exists():
            findings.append(
                AuditFinding(
                    check_id="ir.triage_required",
                    severity=AuditSeverity.ERROR,
                    message="No incident log. Run `fix ir-triage`.",
                    file_path=".core/incident.log",
                    line_number=1,
                )
            )
            return findings

        content = log_path.read_text(encoding="utf-8")
        if "TRIAGED" not in content.upper():
            findings.append(
                AuditFinding(
                    check_id="ir.triage_required",
                    severity=AuditSeverity.ERROR,
                    message="Incident not triaged. Run `fix ir-triage`.",
                    file_path=".core/incident.log",
                    line_number=1,
                )
            )

        return findings
