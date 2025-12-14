# src/mind/governance/checks/refactor_test_check.py
"""
Enforces refactor.requires_tests: Code modifications must be accompanied by test updates.
Ref: standard_code_general (refactor.requires_tests)
"""

from __future__ import annotations

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 8c9d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class RefactorTestCheck(BaseCheck):
    """
    Ensures that commits modifying source code also modify tests.
    This acts as a heuristic for "proof of equivalence" or "verification".
    """

    policy_rule_ids = ["refactor.requires_tests"]

    # ID: ec9d0dda-fedd-4f27-9fbc-e379ab3c0d9a
    def execute(self) -> list[AuditFinding]:
        findings = []

        # 1. Get Git Status
        git_modified_files = getattr(self.context, "git_modified_files", [])

        if not git_modified_files:
            # Full audit or no changes detected; skip heuristic check
            return []

        # 2. Categorize Changes
        src_changes = [
            f for f in git_modified_files if f.startswith("src/") and f.endswith(".py")
        ]

        test_changes = [
            f
            for f in git_modified_files
            if f.startswith("tests/") and f.endswith(".py")
        ]

        # 3. Enforce Rule
        # If source changed but NO tests changed -> Violation
        if src_changes and not test_changes:
            # We group the violation to avoid spamming if 50 files changed
            # But we must report at least one finding per blocking rule

            logger.info(
                "RefactorTestCheck: Found %d source changes but 0 test changes.",
                len(src_changes),
            )

            for file in src_changes:
                findings.append(
                    AuditFinding(
                        check_id="refactor.requires_tests",
                        severity=AuditSeverity.ERROR,
                        message=(
                            "Refactor detected without updated tests. "
                            "Constitutional rule 'refactor.requires_tests' requires proof of verification. "
                            "Update corresponding tests or add new ones."
                        ),
                        file_path=file,
                        line_number=1,
                        context={
                            "test_changes_count": 0,
                            "suggestion": "Run `core-admin coverage remediate` if tests are missing.",
                        },
                    )
                )

        return findings
