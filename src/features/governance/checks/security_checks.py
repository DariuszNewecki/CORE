# src/features/governance/checks/security_checks.py
"""
Scans source code for hardcoded secrets based on configurable detection patterns
and exclusion rules.
"""
from __future__ import annotations

import re

from features.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: e5596ce5-1529-4670-864a-5bd8adfc160d
class SecurityChecks(BaseCheck):
    """Container for security-related constitutional checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        super().__init__(context)
        self.secrets_policy = self.context.policies.get("secrets_management_policy", {})

    # ID: 7c0ecd2a-1bc2-45c9-8da9-48a8b6c35876
    def execute(self) -> list[AuditFinding]:
        """Scans source code for patterns that look like hardcoded secrets."""
        findings = []
        rule = next(
            (
                r
                for r in self.secrets_policy.get("rules", [])
                if r.get("id") == "no_hardcoded_secrets"
            ),
            None,
        )

        if not rule:
            return []

        patterns = rule.get("detection", {}).get("patterns", [])
        exclude_globs = rule.get("detection", {}).get("exclude", [])
        compiled_patterns = [re.compile(p) for p in patterns]

        files_to_scan = {
            s["file_path"] for s in self.context.symbols_list if s.get("file_path")
        }

        for file_path_str in sorted(list(files_to_scan)):
            # --- THIS IS THE FIX ---
            # Use self.repo_root, which is correctly set by the BaseCheck parent class.
            file_path = self.repo_root / file_path_str
            # --- END OF FIX ---
            if any(file_path.match(glob) for glob in exclude_globs):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    for pattern in compiled_patterns:
                        if pattern.search(line):
                            findings.append(
                                AuditFinding(
                                    check_id="security.secrets.hardcoded",
                                    severity=AuditSeverity.ERROR,
                                    message=f"Potential hardcoded secret found on line {i}.",
                                    file_path=str(file_path_str),
                                    line_number=i,
                                )
                            )
            except Exception:
                continue

        return findings
