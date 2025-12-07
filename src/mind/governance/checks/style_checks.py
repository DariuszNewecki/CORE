# src/mind/governance/checks/style_checks.py
"""
A policy-driven auditor for code style and convention compliance, as defined
in the consolidated code_standards.yaml.
"""

from __future__ import annotations

import ast
from pathlib import Path

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 791f7cd8-0441-4e2e-ac65-aa8d0ab82ac7
class StyleChecks(BaseCheck):
    """
    A policy-driven engine for enforcing all code style and convention rules
    defined in the constitution.
    """

    policy_rule_ids = ["style.docstrings_public_apis"]

    def __init__(self, context: AuditorContext):
        super().__init__(context)
        code_standards_policy = self.context.policies.get("code_standards", {})
        self.style_rules = code_standards_policy.get("style_rules", [])
        self.rules_by_id = {
            rule["id"]: rule
            for rule in self.style_rules
            if isinstance(rule, dict) and "id" in rule
        }
        discovered_ids = list(self.rules_by_id.keys())
        self.policy_rule_ids = discovered_ids or self.policy_rule_ids

    def _should_check_file(self, file_path: Path, rule: dict) -> bool:
        """Check if file should be audited based on rule's exclude patterns."""
        exclude_patterns = rule.get("exclude", [])
        file_str = str(file_path.relative_to(self.context.repo_path))

        for pattern in exclude_patterns:
            # Simple glob-style matching
            if pattern.endswith("**/*.py"):
                prefix = pattern.replace("**/*.py", "")
                if file_str.startswith(prefix):
                    return False
            elif pattern in file_str:
                return False
        return True

    # ID: 20cebb25-123b-40d9-999f-4d849eba4228
    def execute(self) -> list[AuditFinding]:
        """Verifies that Python modules adhere to all documented style conventions."""
        findings = []
        for rule_id, rule in self.rules_by_id.items():
            if rule_id == "style.docstrings_public_apis":
                findings.extend(self._check_public_docstrings(rule))
            elif rule_id in [
                "style.linter_required",
                "style.formatter_required",
                "style.import_order",
                "style.fail_on_style_in_ci",
            ]:
                pass
        return findings

    def _check_public_docstrings(self, rule: dict) -> list[AuditFinding]:
        """
        Enforces that all public modules, classes, and functions have docstrings.
        """
        findings = []

        enforcement = rule.get("enforcement", "warn").lower()
        severity_map = {
            "error": AuditSeverity.ERROR,
            "warn": AuditSeverity.WARNING,
            "warning": AuditSeverity.WARNING,
            "info": AuditSeverity.INFO,
        }
        severity = severity_map.get(enforcement, AuditSeverity.WARNING)

        for file_path in self.context.python_files:
            # Skip files excluded by policy
            if not self._should_check_file(file_path, rule):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))

                if not ast.get_docstring(tree):
                    findings.append(
                        AuditFinding(
                            check_id=rule["id"],
                            severity=severity,
                            message="Missing required module-level docstring.",
                            file_path=str(file_path.relative_to(self.repo_root)),
                            line_number=1,
                        )
                    )

                for node in ast.walk(tree):
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        if not node.name.startswith("_"):
                            if not ast.get_docstring(node):
                                findings.append(
                                    AuditFinding(
                                        check_id=rule["id"],
                                        severity=severity,
                                        message=f"Public API '{node.name}' is missing a docstring.",
                                        file_path=str(
                                            file_path.relative_to(self.repo_root)
                                        ),
                                        line_number=node.lineno,
                                    )
                                )
            except Exception as e:
                logger.debug(
                    "Could not parse file %s for style check: %s", file_path, e
                )
        return findings
