# src/system/governance/checks/security_checks.py
"""Auditor checks for security-related policies."""
import re
from pathlib import Path

from system.governance.models import AuditFinding, AuditSeverity


class SecurityChecks:
    """Container for security-related constitutional checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        self.context = context
        self.secrets_policy = self.context.load_config(
            self.context.intent_dir / "policies" / "secrets_management.yaml"
        )

    # CAPABILITY: audit.check.secrets
    def check_for_hardcoded_secrets(self) -> list[AuditFinding]:
        """Scans source code for patterns that look like hardcoded secrets."""
        findings = []
        check_name = "Security: No Hardcoded Secrets"
        rule = next(
            (
                r
                for r in self.secrets_policy.get("rules", [])
                if r["id"] == "no_hardcoded_secrets"
            ),
            None,
        )

        if not rule:
            findings.append(
                AuditFinding(
                    AuditSeverity.WARNING,
                    "Secrets management policy not defined.",
                    check_name,
                )
            )
            return findings

        patterns = rule.get("detection", {}).get("patterns", [])
        exclude_globs = rule.get("detection", {}).get("exclude", [])
        compiled_patterns = [re.compile(p) for p in patterns]

        files_to_scan = [
            Path(s["file"]) for s in self.context.symbols_list if s.get("file")
        ]

        scanned_files_count = 0
        violations_found = 0

        for file_path in set(files_to_scan):
            full_path = self.context.repo_root / file_path
            if any(full_path.match(glob) for glob in exclude_globs):
                continue

            scanned_files_count += 1
            try:
                content = full_path.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    for pattern in compiled_patterns:
                        if pattern.search(line):
                            violations_found += 1
                            findings.append(
                                AuditFinding(
                                    AuditSeverity.ERROR,
                                    f"Potential hardcoded secret found in '{file_path}' on line {i}.",
                                    check_name,
                                    str(file_path),
                                )
                            )
            except Exception:
                continue  # Ignore files that can't be read

        if violations_found == 0:
            findings.append(
                AuditFinding(
                    AuditSeverity.SUCCESS,
                    f"Scanned {scanned_files_count} files; no hardcoded secrets found.",
                    check_name,
                )
            )

        return findings
