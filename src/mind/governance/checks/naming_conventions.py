# src/mind/governance/checks/naming_conventions.py
"""
A constitutional audit check to enforce file and symbol naming conventions.
Aligns with code_standards.yaml v2.0 (Flat Rules Structure).

Ref: .intent/charter/standards/code_standards.json
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

CODE_STANDARDS_POLICY = Path(".intent/charter/standards/code_standards.json")


# ID: naming-conventions-enforcement
# ID: 981f17ff-161b-42c8-97cd-cce83f41c0d3
class NamingConventionsEnforcement(EnforcementMethod):
    """
    Ensures that file names match the patterns defined in the constitution.
    Dynamically loads rules from code_standards.yaml where category='naming'.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: c87d5ad7-912c-47e2-af94-e6b6c05b8efa
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        """
        Runs the check by iterating through loaded naming rules.
        """
        findings = []

        # Load Policy Data
        policy_data = context.policies.get("code_standards", {})

        # 1. Try V2 Format (Flat 'rules' array)
        all_rules = policy_data.get("rules", [])
        naming_rules = [r for r in all_rules if r.get("category") == "naming"]

        # 2. Fallback to Legacy Format (nested 'naming_conventions' dict)
        if not naming_rules:
            legacy_section = policy_data.get("naming_conventions", {})
            if isinstance(legacy_section, dict):
                # Flatten the nested dictionary structure
                for subcategory, rules_list in legacy_section.items():
                    if isinstance(rules_list, list):
                        naming_rules.extend(rules_list)

        if not naming_rules:
            logger.warning(
                "NamingConventionsCheck: No naming rules found in code_standards.yaml"
            )
            return findings

        for rule in naming_rules:
            findings.extend(self._process_rule(context, rule))

        return findings

    def _get_files_for_rule(
        self, context: AuditorContext, rule: dict[str, Any]
    ) -> list[Path]:
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
            for file_path in context.repo_path.glob(pat):
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

    def _process_rule(
        self, context: AuditorContext, rule: dict[str, Any]
    ) -> list[AuditFinding]:
        """Processes a single naming convention rule against its scoped files."""
        findings = []

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
        for file_path in self._get_files_for_rule(context, rule):
            if not compiled_pattern.match(file_path.name):
                findings.append(
                    AuditFinding(
                        check_id=rule_id,
                        severity=severity,
                        message=(
                            f"Naming Violation: '{file_path.name}' does not match pattern '{pattern_str}'."
                        ),
                        file_path=str(file_path.relative_to(context.repo_path)),
                    )
                )
        return findings


# ID: 7cff5dba-bd63-4e8c-8e3f-8f242a59f28d
class NamingConventionsCheck(RuleEnforcementCheck):
    """
    Ensures that file names match the patterns defined in the constitution.
    Dynamically loads rules from code_standards.yaml where category='naming'.

    Ref: .intent/charter/standards/code_standards.json
    """

    # Explicitly declared IDs from code_standards.yaml v2.0
    policy_rule_ids: ClassVar[list[str]] = [
        "intent.policy_file_naming",
    ]

    policy_file: ClassVar[Path] = CODE_STANDARDS_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        NamingConventionsEnforcement(rule_id="intent.policy_file_naming"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
