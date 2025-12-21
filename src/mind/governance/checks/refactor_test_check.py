# src/mind/governance/checks/refactor_test_check.py
"""
Enforces refactor.requires_tests: Code modifications must be accompanied by test updates.

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
from shared.logger import getLogger
from shared.models import AuditFinding


logger = getLogger(__name__)


# ID: refactor-test-enforcement
# ID: b3c4d5e6-f7a8-4b3c-9d8e-7f6a5b4c3d2e
class RefactorTestEnforcement(EnforcementMethod):
    """Verifies that source changes are accompanied by test changes."""

    # ID: 724749d5-9b47-469e-95f8-a655eed506ac
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        git_modified_files = getattr(context, "git_modified_files", [])

        if not git_modified_files:
            return []

        src_changes = [
            f for f in git_modified_files if f.startswith("src/") and f.endswith(".py")
        ]

        test_changes = [
            f
            for f in git_modified_files
            if f.startswith("tests/") and f.endswith(".py")
        ]

        if src_changes and not test_changes:
            logger.info(
                "RefactorTestCheck: Found %d source changes but 0 test changes.",
                len(src_changes),
            )

            for file in src_changes:
                findings.append(
                    self._create_finding(
                        message=(
                            "Refactor detected without updated tests. "
                            "Constitutional rule 'refactor.requires_tests' requires proof of verification. "
                            "Update corresponding tests or add new ones."
                        ),
                        file_path=file,
                        line_number=1,
                    )
                )

        return findings


# ID: 8c9d1e2f-3a4b-5c6d-7e8f-9a0b1c2d3e4f
class RefactorTestCheck(RuleEnforcementCheck):
    """
    Enforces refactor.requires_tests.
    Ref: .intent/charter/standards/code_standards.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["refactor.requires_tests"]

    policy_file: ClassVar = settings.paths.policy("code_standards")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        RefactorTestEnforcement(rule_id="refactor.requires_tests"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
