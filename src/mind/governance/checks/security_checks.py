# src/mind/governance/checks/security_checks.py
"""
Scans source code for security vulnerabilities.
Driven by configuration in data_governance.yaml and safety.yaml.
Supports both Legacy (nested) and v2 (flat rules) policy structures.
"""

from __future__ import annotations

import ast
import fnmatch
import re
from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 80baca41-4809-456b-985b-9bb9a6cebb7b
class SecurityChecks(BaseCheck):
    """
    A policy-driven check that enforces security/safety rules defined in the Constitution.
    Dynamically loads rules from 'data_governance' and 'safety_framework'.
    """

    # Safe fallback
    policy_rule_ids = ["secrets.no_hardcoded_secrets", "safety.no_dangerous_execution"]

    def __init__(self, context: AuditorContext):
        """Initializes the check and dynamically discovers the rules it must enforce."""
        super().__init__(context)

        # Policies to inspect
        target_policies = [
            "data_governance",
            "safety_framework",
            "standard_operations_safety",
        ]

        self.rules_by_id: dict[str, Any] = {}

        for policy_name in target_policies:
            policy_data = self.context.policies.get(policy_name, {})
            if not policy_data:
                continue

            # 1. v2 Standard: Flat 'rules' array
            if "rules" in policy_data and isinstance(policy_data["rules"], list):
                for rule in policy_data["rules"]:
                    if self._is_security_rule(rule):
                        self.rules_by_id[rule["id"]] = rule

            # 2. Legacy: Nested sections (security_rules, safety_rules)
            for section in ["security_rules", "safety_rules"]:
                if section in policy_data and isinstance(policy_data[section], list):
                    for rule in policy_data[section]:
                        if isinstance(rule, dict) and rule.get("id"):
                            self.rules_by_id[rule["id"]] = rule

        # Update contract
        if self.rules_by_id:
            self.policy_rule_ids = list(self.rules_by_id.keys())

    def _is_security_rule(self, rule: dict) -> bool:
        """Heuristic to determine if a generic rule is a security rule."""
        # Checks if it has detection configuration or specific categories
        if rule.get("detection"):
            return True
        category = rule.get("category", "")
        return category in ("security", "safety", "secrets")

    # ID: cb2146e9-2abb-4982-ac11-31f118a10707
    def execute(self) -> list[AuditFinding]:
        """Scans source code for violations of any configured security rule."""
        findings = []

        for rule_id, rule in self.rules_by_id.items():
            detection = rule.get("detection", {})
            method = detection.get("method")

            try:
                if method == "regex_scan":
                    findings.extend(self._scan_with_regex(rule))
                elif method == "ast_call_scan":
                    findings.extend(self._scan_for_dangerous_calls(rule))
                # Future: 'file_scan' for permissions, etc.
            except Exception as e:
                logger.error("Security check failed for rule '%s': %s", rule_id, e)

        return findings

    def _get_files_to_scan(self, rule: dict[str, Any]) -> list[Path]:
        """Gets a list of Python files to scan, respecting rule exclusions."""
        exclude_globs = rule.get("detection", {}).get("exclude", [])
        files_to_scan = []

        for file_path in self.context.python_files:
            rel_path_str = str(file_path.relative_to(self.repo_root))

            # Check exclusions
            if any(fnmatch.fnmatch(rel_path_str, glob) for glob in exclude_globs):
                continue

            files_to_scan.append(file_path)

        return files_to_scan

    def _get_severity(self, rule: dict) -> AuditSeverity:
        """Safely parse severity string to Enum."""
        val = rule.get("enforcement", "error").upper()
        if val == "WARN":
            val = "WARNING"
        try:
            return AuditSeverity[val]
        except KeyError:
            return AuditSeverity.ERROR

    def _scan_with_regex(self, rule: dict[str, Any]) -> list[AuditFinding]:
        """Generic scanner for rules using regex patterns."""
        findings = []
        rule_id = rule["id"]
        patterns = []

        for p in rule.get("detection", {}).get("patterns", []):
            try:
                patterns.append(re.compile(p))
            except re.error:
                logger.warning("Invalid regex in rule %s: %s", rule_id, p)

        if not patterns:
            return []

        for file_path in self._get_files_to_scan(rule):
            try:
                content = file_path.read_text(encoding="utf-8")
                lines = content.splitlines()

                for i, line in enumerate(lines, 1):
                    # Optimization: skip comments if rule allows (not implemented here for safety)
                    for pattern in patterns:
                        if pattern.search(line):
                            findings.append(
                                AuditFinding(
                                    check_id=rule_id,
                                    severity=self._get_severity(rule),
                                    message=f"Security Violation ({rule_id}): Pattern match found.",
                                    file_path=str(
                                        file_path.relative_to(self.repo_root)
                                    ),
                                    line_number=i,
                                    context={
                                        "pattern": pattern.pattern,
                                        "match": line.strip(),
                                    },
                                )
                            )
            except Exception:
                continue

        return findings

    def _scan_for_dangerous_calls(self, rule: dict[str, Any]) -> list[AuditFinding]:
        """Generic scanner for dangerous function calls via AST."""
        findings = []
        rule_id = rule["id"]

        # Compile regexes for function names (e.g. "subprocess\..*")
        patterns = []
        for p in rule.get("detection", {}).get("patterns", []):
            try:
                patterns.append(re.compile(p))
            except re.error:
                logger.warning("Invalid regex in rule %s: %s", rule_id, p)

        if not patterns:
            return []

        for file_path in self._get_files_to_scan(rule):
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call):
                        # Extract function name (e.g. "eval" or "subprocess.run")
                        call_name = self._get_call_name(node)

                        if call_name:
                            for pattern in patterns:
                                if pattern.search(call_name):
                                    findings.append(
                                        AuditFinding(
                                            check_id=rule_id,
                                            severity=self._get_severity(rule),
                                            message=f"Security Violation ({rule_id}): Dangerous call '{call_name}'.",
                                            file_path=str(
                                                file_path.relative_to(self.repo_root)
                                            ),
                                            line_number=node.lineno,
                                        )
                                    )
            except Exception:
                continue

        return findings

    def _get_call_name(self, node: ast.Call) -> str:
        """Extract name of function being called."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            # Resolve one level of attribute (obj.method)
            # Full resolution requires a recursive visitor, keeping it simple here
            if isinstance(node.func.value, ast.Name):
                return f"{node.func.value.id}.{node.func.attr}"
        return ""
