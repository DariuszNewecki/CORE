# src/mind/governance/checks/naming_conventions.py
"""
A constitutional audit check to enforce file and symbol naming conventions
as defined in the code_standards.yaml policy.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

logger = getLogger(__name__)


# ID: 7cff5dba-bd63-4e8c-8e3f-8f242a59f28d
class NamingConventionsCheck(BaseCheck):
    """
    Ensures that file names match the patterns defined in the constitution.
    This check is fully dynamic and reads all configuration from the policy file.
    """

    # Fallback: at least one rule id so the check is linkable in governance
    policy_rule_ids = ["intent.policy_file_naming"]

    def __init__(self, context: AuditorContext) -> None:
        super().__init__(context)

        # Ensure we respect the repo_root provided by the AuditorContext.
        # This is critical for tests that run in a temporary directory.
        if getattr(self.context, "repo_root", None) is not None:
            self.repo_root = Path(self.context.repo_root)

        code_standards_policy = self.context.policies.get("code_standards", {})
        self.naming_policy: dict[str, Any] = code_standards_policy.get(
            "naming_conventions", {}
        )

        # --- Dynamic Constitutional Linkage ---
        # Collect all rule IDs so the check can be traced back to specific policy rules.
        all_rule_ids: list[str] = []
        for rules in self.naming_policy.values():
            if isinstance(rules, list):
                for rule in rules:
                    if isinstance(rule, dict) and rule.get("id"):
                        all_rule_ids.append(rule["id"])

        # If we found rule ids in the policy, expose them; otherwise keep the fallback.
        self.policy_rule_ids = all_rule_ids or self.policy_rule_ids

    # ID: 6bebb819-1073-4163-8b70-09c2c374f6c8
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by iterating through policy rules and scanning the
        repository file system for violations.
        """
        findings: list[AuditFinding] = []

        if not self.naming_policy:
            return findings

        for category, rules in self.naming_policy.items():
            if not isinstance(rules, list):
                continue

            for rule in rules:
                if not isinstance(rule, dict):
                    continue
                findings.extend(self._process_rule(rule, category))

        return findings

    # --- START OF FIX ---
    def _get_files_for_rule(self, rule: dict[str, Any]) -> list[Path]:
        """
        Gets all files that a rule applies to, respecting its scope and exclusions.
        This function encapsulates the file-gathering logic.
        """
        scope_glob = rule.get("scope")
        if not scope_glob:
            return []

        exclusions = rule.get("exclusions", [])
        if not isinstance(exclusions, (list, tuple, set)):
            exclusions = [exclusions]
        exclusions = list(exclusions)

        candidate_files: list[Path] = []
        for file_path in self.repo_root.glob(scope_glob):
            if not file_path.is_file():
                continue

            # Check against exclusion patterns.
            is_excluded = False
            for ex_pattern in exclusions:
                if file_path.name == ex_pattern or file_path.match(ex_pattern):
                    is_excluded = True
                    break
            if not is_excluded:
                candidate_files.append(file_path)

        return candidate_files

    def _process_rule(self, rule: dict[str, Any], category: str) -> list[AuditFinding]:
        """Processes a single naming convention rule against its scoped files."""
        findings: list[AuditFinding] = []

        pattern_str = rule.get("pattern")
        rule_id = rule.get("id")
        enforcement = rule.get("enforcement", "error")

        if not pattern_str or not rule_id:
            return findings

        try:
            compiled_pattern = re.compile(pattern_str)
        except re.error:
            logger.warning(
                "Invalid regex pattern for naming rule '%s': %s", rule_id, pattern_str
            )
            return findings

        try:
            severity = AuditSeverity[enforcement.upper()]
        except KeyError:
            logger.warning(
                "Unknown enforcement level '%s' for naming rule '%s'; defaulting to WARN",
                enforcement,
                rule_id,
            )
            severity = AuditSeverity.WARNING

        # Use the dedicated helper to get only the files this rule applies to.
        for file_path in self._get_files_for_rule(rule):
            if not compiled_pattern.match(file_path.name):
                findings.append(
                    AuditFinding(
                        check_id=rule_id,
                        severity=severity,
                        message=(
                            f"File name '{file_path.name}' violates naming "
                            f"convention '{rule_id}'. Expected pattern: {pattern_str}"
                        ),
                        file_path=str(file_path.relative_to(self.repo_root)),
                    )
                )
        return findings

    # --- END OF FIX ---
