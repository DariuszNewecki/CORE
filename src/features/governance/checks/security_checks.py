# src/features/governance/checks/security_checks.py
"""
Scans source code for hardcoded secrets and other security vulnerabilities
based on configurable detection patterns and exclusion rules.
"""

from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path

from features.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: e5596ce5-1529-4670-864a-5bd8adfc160d
class SecurityChecks(BaseCheck):
    """Container for security-related constitutional checks."""

    def __init__(self, context):
        """Initializes the check with a shared auditor context."""
        super().__init__(context)
        self.secrets_policy = self.context.policies.get("secrets_management_policy", {})
        self.safety_policy = self.context.policies.get("safety_policy", {})

    # ID: 7c0ecd2a-1bc2-45c9-8da9-48a8b6c35876
    def execute(self) -> list[AuditFinding]:
        """Scans source code for hardcoded secrets and other security vulnerabilities."""
        findings = []
        findings.extend(self._check_for_hardcoded_secrets())
        findings.extend(self._check_dangerous_calls())
        findings.extend(self._check_unsafe_imports())
        return findings

    def _get_files_to_scan(self, rule: dict) -> list[Path]:
        """Gets a list of Python files to scan, respecting rule exclusions."""
        exclude_globs = rule.get("scope", {}).get("exclude", [])
        exclude_paths = [exc.get("path") for exc in exclude_globs if exc.get("path")]

        files_to_scan = []
        for file_path in self.context.python_files:
            if not file_path.is_file():
                continue
            rel_path_str = str(file_path.relative_to(self.repo_root))
            if any(fnmatch.fnmatch(rel_path_str, glob) for glob in exclude_paths):
                continue
            files_to_scan.append(file_path)
        return files_to_scan

    def _check_for_hardcoded_secrets(self) -> list[AuditFinding]:
        """Scans for hardcoded secrets."""
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

        findings = []
        patterns = rule.get("detection", {}).get("patterns", [])
        exclude_globs = rule.get("detection", {}).get("exclude", [])
        compiled_patterns = [re.compile(p) for p in patterns]

        for file_path in self.context.python_files:
            # --- THIS IS THE FIX ---
            # Use fnmatch here as well for consistency and correctness.
            rel_path_str = str(file_path.relative_to(self.repo_root))
            if any(fnmatch.fnmatch(rel_path_str, glob) for glob in exclude_globs):
                continue
            # --- END OF FIX ---

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
                                    file_path=str(
                                        file_path.relative_to(self.repo_root)
                                    ),
                                    line_number=i,
                                )
                            )
            except Exception:
                continue
        return findings

    def _check_dangerous_calls(self) -> list[AuditFinding]:
        """Scans for dangerous function calls based on the safety policy."""
        rule = next(
            (
                r
                for r in self.safety_policy.get("rules", [])
                if r.get("id") == "no_dangerous_execution"
            ),
            None,
        )
        if not rule:
            return []

        findings = []
        patterns = [
            re.compile(p) for p in rule.get("detection", {}).get("patterns", [])
        ]
        files_to_scan = self._get_files_to_scan(rule)

        for file_path in files_to_scan:
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        call_str = ast.unparse(node.func)
                        for pattern in patterns:
                            if pattern.search(call_str):
                                findings.append(
                                    AuditFinding(
                                        check_id="security.dangerous.call",
                                        severity=AuditSeverity.ERROR,
                                        message=f"Use of dangerous call pattern: '{call_str}'",
                                        file_path=str(
                                            file_path.relative_to(self.repo_root)
                                        ),
                                        line_number=node.lineno,
                                    )
                                )
            except Exception:
                continue
        return findings

    def _check_unsafe_imports(self) -> list[AuditFinding]:
        """Scans for forbidden imports based on the safety policy."""
        rule = next(
            (
                r
                for r in self.safety_policy.get("rules", [])
                if r.get("id") == "no_unsafe_imports"
            ),
            None,
        )
        if not rule:
            return []

        findings = []
        forbidden_imports = set(rule.get("detection", {}).get("forbidden", []))
        files_to_scan = self._get_files_to_scan(rule)

        for file_path in files_to_scan:
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in forbidden_imports:
                                findings.append(
                                    AuditFinding(
                                        check_id="security.dangerous.import",
                                        severity=AuditSeverity.ERROR,
                                        message=f"Import of forbidden module: '{alias.name}'",
                                        file_path=str(
                                            file_path.relative_to(self.repo_root)
                                        ),
                                        line_number=node.lineno,
                                    )
                                )
                    elif (
                        isinstance(node, ast.ImportFrom)
                        and node.module in forbidden_imports
                    ):
                        findings.append(
                            AuditFinding(
                                check_id="security.dangerous.import",
                                severity=AuditSeverity.ERROR,
                                message=f"Import from forbidden module: '{node.module}'",
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=node.lineno,
                            )
                        )
            except Exception:
                continue
        return findings
