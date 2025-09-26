# src/features/governance/checks/naming_conventions.py
"""
A constitutional audit check to enforce file and symbol naming conventions
as defined in the naming_conventions_policy.yaml.
"""
from __future__ import annotations

import re
from typing import List

from features.governance.audit_context import AuditorContext
from shared.models import AuditFinding, AuditSeverity


# ID: 48100636-3970-4d7b-835a-1a4279ef3717
class NamingConventionsCheck:
    """
    Ensures that file names match the patterns defined in the constitution.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        self.policy = self.context.policies.get("naming_conventions_policy", {})

    # ID: 3ceda015-448e-4745-9b09-573cc37edeb1
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check by scanning all repository files against the policy rules.
        """
        findings = []
        rules = self.policy.get("rules", [])
        if not rules:
            return findings

        for rule in rules:
            scope_glob = rule.get("scope", "**/*")
            pattern = rule.get("pattern")
            exclusions = rule.get("exclusions", [])

            if not pattern:
                continue

            try:
                compiled_pattern = re.compile(pattern)
            except re.error:
                # Invalid regex in policy, skip this rule
                continue

            for file_path in self.context.repo_path.glob(scope_glob):
                if not file_path.is_file():
                    continue

                # Check against exclusions
                if any(file_path.match(ex) for ex in exclusions):
                    continue

                if not compiled_pattern.match(file_path.name):
                    findings.append(
                        AuditFinding(
                            check_id=f"naming.{rule.get('id', 'unnamed_rule')}",
                            severity=AuditSeverity.ERROR,
                            message=f"File name '{file_path.name}' violates naming convention. Expected pattern: {pattern}",
                            file_path=str(
                                file_path.relative_to(self.context.repo_path)
                            ),
                        )
                    )
        return findings
