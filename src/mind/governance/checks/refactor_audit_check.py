# src/mind/governance/checks/refactor_audit_check.py
"""
Enforces refactor.audit_after: run constitutional audit after any refactor.
"""

from __future__ import annotations

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: a1b2c3d4-e5f6-4a3b-9c8d-7e6f5a4b3c2d
class RefactorAuditCheck(BaseCheck):
    policy_rule_ids = ["refactor.audit_after"]

    # ID: d6e6c495-5c72-4ba5-a7f9-7831f003abfa
    def execute(self) -> list[AuditFinding]:
        findings = []

        # Any Python file in src/ modified?
        src_changes = [
            f
            for f in self.context.git_modified_files
            if f.startswith("src/") and f.endswith(".py")
        ]
        if not src_changes:
            return findings

        # Was audit run recently? (Check for audit log in last 5 mins)
        import time
        from pathlib import Path

        audit_log = Path(".core/audit.log")
        if not audit_log.exists():
            for file in src_changes:
                findings.append(
                    AuditFinding(
                        check_id="refactor.audit_after",
                        severity=AuditSeverity.ERROR,
                        message="Code refactored without running 'core-admin check audit'.",
                        file_path=file,
                        line_number=1,
                    )
                )
            return findings

        # If audit log exists but too old
        if time.time() - audit_log.stat().st_mtime > 300:  # 5 minutes
            for file in src_changes:
                findings.append(
                    AuditFinding(
                        check_id="refactor.audit_after",
                        severity=AuditSeverity.ERROR,
                        message="Refactor detected, but audit is stale (>5 min). Run 'check audit'.",
                        file_path=file,
                        line_number=1,
                    )
                )

        return findings
