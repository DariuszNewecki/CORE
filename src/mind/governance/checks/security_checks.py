# src/mind/governance/checks/security_checks.py
"""
Scans source code for security vulnerabilities based on configurable rules
defined in the data_governance and safety_framework policies.
"""

from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck

logger = getLogger(__name__)


# ID: 80baca41-4809-456b-985b-9bb9a6cebb7b
class SecurityChecks(BaseCheck):
    """
    A policy-driven check that enforces all security and safety rules
    defined in the constitution.
    """

    # ← Declare at class level with safe fallback
    policy_rule_ids = ["secrets.no_hardcoded_secrets"]  # at least one known rule

    def __init__(self, context: AuditorContext):
        """Initializes the check and dynamically discovers the rules it must enforce."""
        super().__init__(context)

        data_gov_policy = self.context.policies.get("data_governance", {})
        safety_framework = self.context.policies.get("safety_framework", {})

        # Consolidate all security-related rules into a single lookup table
        self.rules_by_id: dict[str, Any] = {
            rule["id"]: rule
            for policy in [data_gov_policy, safety_framework]
            for section in ["security_rules", "safety_rules"]
            for rule in policy.get(section, [])
            if isinstance(rule, dict) and rule.get("id")
        }

        # Dynamically set the constitutional contract
        discovered_ids = list(self.rules_by_id.keys())
        self.policy_rule_ids = (
            discovered_ids or self.policy_rule_ids
        )  # use fallback if empty

    # ID: cb2146e9-2abb-4982-ac11-31f118a10707
    def execute(self) -> list[AuditFinding]:
        """
        Scans source code for violations of any configured security rule.
        """
        findings = []
        # The logic is now a generic loop over all discovered rules.
        for rule_id, rule in self.rules_by_id.items():
            detection_method = rule.get("detection", {}).get("method")
            if detection_method == "regex_scan":
                findings.extend(self._scan_with_regex(rule))
            elif detection_method == "ast_call_scan":
                findings.extend(self._scan_for_dangerous_calls(rule))
            # Add other detection methods here as needed.
        return findings

    def _get_files_to_scan(self, rule: dict[str, Any]) -> list[Path]:
        """Gets a list of Python files to scan, respecting rule exclusions."""
        exclude_globs = rule.get("detection", {}).get("exclude", [])
        files_to_scan = []
        for file_path in self.context.python_files:
            rel_path_str = str(file_path.relative_to(self.repo_root))
            if any(fnmatch.fnmatch(rel_path_str, glob) for glob in exclude_globs):
                continue
            files_to_scan.append(file_path)
        return files_to_scan

    def _scan_with_regex(self, rule: dict[str, Any]) -> list[AuditFinding]:
        """Generic scanner for rules using regex patterns on file content."""
        findings = []
        rule_id = rule["id"]
        patterns = [
            re.compile(p) for p in rule.get("detection", {}).get("patterns", [])
        ]
        if not patterns:
            return []

        for file_path in self._get_files_to_scan(rule):
            try:
                content = file_path.read_text(encoding="utf-8")
                for i, line in enumerate(content.splitlines(), 1):
                    for pattern in patterns:
                        if pattern.search(line):
                            findings.append(
                                AuditFinding(
                                    check_id=rule_id,
                                    severity=AuditSeverity[
                                        rule.get("enforcement", "error").upper()
                                    ],
                                    message=f"Potential security violation of '{rule_id}' found.",
                                    file_path=str(
                                        file_path.relative_to(self.repo_root)
                                    ),
                                    line_number=i,
                                    context={"pattern": pattern.pattern},
                                )
                            )
            except Exception as exc:
                logger.debug(
                    "Failed regex scan for rule %s on file %s: %s",
                    rule_id,
                    file_path,
                    exc,
                )
        return findings

    def _scan_for_dangerous_calls(self, rule: dict[str, Any]) -> list[AuditFinding]:
        """Generic scanner for rules looking for dangerous function calls via AST."""
        findings = []
        rule_id = rule["id"]
        patterns = [
            re.compile(p) for p in rule.get("detection", {}).get("patterns", [])
        ]
        if not patterns:
            return []

        for file_path in self._get_files_to_scan(rule):
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))
                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        # ast.unparse is a reliable way to get the function call name
                        call_str = ast.unparse(node.func)
                        for pattern in patterns:
                            if pattern.search(call_str):
                                findings.append(
                                    AuditFinding(
                                        check_id=rule_id,
                                        severity=AuditSeverity[
                                            rule.get("enforcement", "error").upper()
                                        ],
                                        message=f"Dangerous call pattern found violating '{rule_id}': '{call_str}'",
                                        file_path=str(
                                            file_path.relative_to(self.repo_root)
                                        ),
                                        line_number=node.lineno,
                                    )
                                )
            except Exception as exc:
                logger.debug(
                    "Failed AST scan for rule %s on file %s: %s",
                    rule_id,
                    file_path,
                    exc,
                )
        return findings
