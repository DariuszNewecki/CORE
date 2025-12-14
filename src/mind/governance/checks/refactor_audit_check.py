# src/mind/governance/checks/refactor_audit_check.py
"""
Enforces refactor.audit_after: Verifies that an audit is running against modified files.
Acts as a 'Compliance Signature' for the audit trail.
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: a1b2c3d4-e5f6-4a3b-9c8d-7e6f5a4b3c2d
class RefactorAuditCheck(BaseCheck):
    """
    Detects source code modifications and explicitly records that
    the current audit session is validating them.
    Ref: standard_code_general (refactor.audit_after)
    """

    policy_rule_ids = ["refactor.audit_after"]

    # ID: d6e6c495-5c72-4ba5-a7f9-7831f003abfa
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        # 1. Get Git Status from Context
        # The AuditorContext should be populated with git status by the runner
        git_modified_files = getattr(self.context, "git_modified_files", [])

        if git_modified_files is None:
            # Context wasn't loaded with git info (e.g. partial run)
            return []

        # 2. Filter for Source Changes (Body Layer)
        src_changes = [
            f for f in git_modified_files if f.startswith("src/") and f.endswith(".py")
        ]

        if not src_changes:
            return findings

        # 3. Generate Compliance Signature
        # Instead of blocking (ERROR), we emit an INFO finding that serves
        # as the permanent record that these specific changes were audited.

        # We group them into one finding to avoid noise
        file_list_str = "\n".join(f"- {f}" for f in src_changes[:5])
        if len(src_changes) > 5:
            file_list_str += f"\n...and {len(src_changes) - 5} more."

        findings.append(
            AuditFinding(
                check_id="refactor.audit_after",
                severity=AuditSeverity.INFO,  # Info = Record of Compliance
                message=(
                    f"Refactor Detected. This audit run validates the following changes:\n"
                    f"{file_list_str}"
                ),
                file_path="src/",  # General scope
                context={
                    "modified_files": src_changes,
                    "validation_status": "in_progress",
                },
            )
        )

        return findings
