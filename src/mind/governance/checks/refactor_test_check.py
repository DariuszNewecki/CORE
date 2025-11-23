# src/mind/governance/checks/refactor_test_check.py
"""
Enforces refactor.requires_tests: no refactored code without updated tests.
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 8c9d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class RefactorTestCheck(BaseCheck):
    policy_rule_ids = ["refactor.requires_tests"]

    # ID: ec9d0dda-fedd-4f27-9fbc-e379ab3c0d9a
    def execute(self) -> list[AuditFinding]:
        findings = []

        # --- START OF FIX ---
        # Safely get the list of modified files. Default to an empty list if the
        # attribute doesn't exist (e.g., in a full audit context).
        git_modified_files = getattr(self.context, "git_modified_files", [])
        # --- END OF FIX ---

        src_changes = [
            f
            for f in git_modified_files  # Use the safe local variable
            if f.startswith("src/") and f.endswith(".py") and "tests/" not in f
        ]
        if not src_changes:
            return findings

        test_changes = [
            f
            for f in git_modified_files  # Use the safe local variable
            if f.startswith("tests/") and f.endswith(".py")
        ]

        if not test_changes:
            for file in src_changes:
                findings.append(
                    AuditFinding(
                        check_id="refactor.requires_tests",
                        severity=AuditSeverity.ERROR,
                        message="Refactored code without updated tests.",
                        file_path=file,
                        line_number=1,
                    )
                )

        return findings
