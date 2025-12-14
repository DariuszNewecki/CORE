# src/mind/governance/checks/naming_conventions.py
"""
A constitutional audit check to enforce file and symbol naming conventions.
Aligns with code_standards.yaml v2.0 (Flat Rules Structure).
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
    Dynamically loads rules from code_standards.yaml where category='naming'.
    """

    # Explicitly declared IDs from code_standards.yaml v2.0
    policy_rule_ids = [
        "intent.policy_file_naming",
        "intent.policy_schema_naming",
        "intent.artifact_schema_naming",
        "intent.prompt_file_naming",
        "intent.proposal_file_naming",
        "code.python_module_naming",
        "code.python_test_module_naming",
    ]

    def __init__(self, context: AuditorContext) -> None:
        super().__init__(context)

        # Load Flat Rules from code_standards (v2 Structure)
        policy_data = self.context.policies.get("code_standards", {})
        all_rules = policy_data.get("rules", [])

        # Filter for naming rules
        self.naming_rules = [r for r in all_rules if r.get("category") == "naming"]

        if not self.naming_rules:
            logger.warning(
                "NamingConventionsCheck: No rules with category='naming' found in code_standards.yaml."
            )

    # ID: 6bebb819-1073-4163-8b70-09c2c374f6c8
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by iterating through loaded naming rules.
        """
        findings: list[AuditFinding] = []

        for rule in self.naming_rules:
            findings.extend(self._process_rule(rule))

        return findings

    def _get_files_for_rule(self, rule: dict[str, Any]) -> list[Path]:
        """
        Gets all files that a rule applies to, respecting its scope and exclusions.
        """
        scope_glob = rule.get("scope")
        if not scope_glob:
            return []

        # Handle scope being a list or string
        if isinstance(scope_glob, list):
            scopes = scope_glob
        else:
            scopes = [scope_glob]

        exclusions = rule.get("exclusions", [])
        if not isinstance(exclusions, (list, tuple, set)):
            exclusions = [exclusions]

        candidate_files: set[Path] = set()

        for pat in scopes:
            # Recursive globbing handled by pathlib if '**' is in pattern
            for file_path in self.repo_root.glob(pat):
                if not file_path.is_file():
                    continue

                # Check exclusions
                is_excluded = False
                for ex_pattern in exclusions:
                    # Match name or full path match
                    if file_path.name == ex_pattern or file_path.match(ex_pattern):
                        is_excluded = True
                        break

                if not is_excluded:
                    candidate_files.add(file_path)

        return list(candidate_files)

    def _process_rule(self, rule: dict[str, Any]) -> list[AuditFinding]:
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

        # Map 'warn' -> WARNING, 'error' -> ERROR
        sev_str = enforcement.upper()
        if sev_str == "WARN":
            sev_str = "WARNING"

        try:
            severity = AuditSeverity[sev_str]
        except KeyError:
            severity = AuditSeverity.WARNING

        # Validate files
        for file_path in self._get_files_for_rule(rule):
            if not compiled_pattern.match(file_path.name):
                findings.append(
                    AuditFinding(
                        check_id=rule_id,
                        severity=severity,
                        message=(
                            f"Naming Violation: '{file_path.name}' does not match pattern '{pattern_str}'."
                        ),
                        file_path=str(file_path.relative_to(self.repo_root)),
                    )
                )
        return findings
