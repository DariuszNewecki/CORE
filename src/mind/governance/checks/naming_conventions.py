# src/mind/governance/checks/naming_conventions.py
"""
A constitutional audit check to enforce file and symbol naming conventions
as defined in the code_standards.yaml policy.
"""

from __future__ import annotations

import re
from typing import Any

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck

logger = getLogger(__name__)


# ID: 7cff5dba-bd63-4e8c-8e3f-8f242a59f28d
class NamingConventionsCheck(BaseCheck):
    """
    Ensures that file names match the patterns defined in the constitution.
    This check is fully dynamic and reads all configuration from the policy file.
    """

    # ← Declare at class level with safe fallback
    policy_rule_ids = ["intent.policy_file_naming"]  # fallback: at least one rule

    def __init__(self, context: AuditorContext):
        super().__init__(context)

        code_standards_policy = self.context.policies.get("code_standards", {})
        self.naming_policy = code_standards_policy.get("naming_conventions", {})

        # --- Dynamic Constitutional Linkage ---
        all_rule_ids = []
        for rules in self.naming_policy.values():
            if isinstance(rules, list):
                for rule in rules:
                    if isinstance(rule, dict) and rule.get("id"):
                        all_rule_ids.append(rule["id"])

        # ← Now safe: update instance-level policy_rule_ids
        self.policy_rule_ids = (
            all_rule_ids or self.policy_rule_ids
        )  # keep fallback if empty

    # ID: 6bebb819-1073-4163-8b70-09c2c374f6c8
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by iterating through policy rules and scanning the
        repository file system for violations.
        """
        findings = []
        if not self.naming_policy:
            return findings

        for category, rules in self.naming_policy.items():
            if not isinstance(rules, list):
                continue
            for rule in rules:
                findings.extend(self._process_rule(rule, category))
        return findings

    def _process_rule(self, rule: dict[str, Any], category: str) -> list[AuditFinding]:
        """Processes a single naming convention rule against the file system."""
        findings = []
        scope_glob = rule.get("scope")
        pattern = rule.get("pattern")
        rule_id = rule.get("id")
        exclusions = rule.get("exclusions", [])
        enforcement = rule.get("enforcement", "error")

        if not scope_glob or not pattern or not rule_id:
            return findings  # Skip malformed rules

        try:
            compiled_pattern = re.compile(pattern)
        except re.error:
            logger.warning(
                "Invalid regex pattern for naming rule '%s': %s", rule_id, pattern
            )
            return findings

        for file_path in self.repo_root.glob(scope_glob):
            if not file_path.is_file():
                continue
            if any(file_path.match(ex) for ex in exclusions):
                continue

            if not compiled_pattern.match(file_path.name):
                findings.append(
                    AuditFinding(
                        check_id=rule_id,
                        severity=AuditSeverity[enforcement.upper()],
                        message=(
                            f"File name '{file_path.name}' violates naming convention '{rule_id}'. "
                            f"Expected pattern: {pattern}"
                        ),
                        file_path=str(file_path.relative_to(self.repo_root)),
                    )
                )
        return findings
