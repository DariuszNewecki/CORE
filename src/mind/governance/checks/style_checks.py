# src/mind/governance/checks/style_checks.py
"""
A policy-driven auditor for code style and convention compliance.
Enforces 'style.*' rules from code_standards.yaml (v2 Structure).
"""

from __future__ import annotations

import ast
import fnmatch
from pathlib import Path

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 791f7cd8-0441-4e2e-ac65-aa8d0ab82ac7
class StyleChecks(BaseCheck):
    """
    Enforces AST-based style rules defined in the constitution.
    Primarily checks docstrings coverage and Pythonic conventions.
    """

    # Default contract
    policy_rule_ids = ["style.docstrings_public_apis"]

    def __init__(self, context: AuditorContext):
        super().__init__(context)

        # Load v2 Flat Rules
        policy = self.context.policies.get("code_standards", {})
        all_rules = policy.get("rules", [])

        # Filter for Style category
        self.style_rules = {
            r["id"]: r for r in all_rules if r.get("category") == "style"
        }

        # Update contract
        if self.style_rules:
            self.policy_rule_ids = list(self.style_rules.keys())

    def _is_file_in_scope(self, file_path: Path, rule: dict) -> bool:
        """
        Determines if file is within the rule's scope using glob patterns.
        Ref: RULES-STRUCTURE.yaml
        """
        rel_path = str(file_path.relative_to(self.repo_root)).replace("\\", "/")

        # 1. Check Scope (Default to src/**/*.py if missing)
        scopes = rule.get("scope", ["src/**/*.py"])
        if isinstance(scopes, str):
            scopes = [scopes]

        in_scope = False
        for pattern in scopes:
            if fnmatch.fnmatch(rel_path, pattern):
                in_scope = True
                break

        if not in_scope:
            return False

        # 2. Check Exceptions/Exclusions
        # v2 uses 'exceptions', v1 used 'exclude'. Support both.
        exclusions = rule.get("exceptions", []) or rule.get("exclude", [])
        if isinstance(exclusions, str):
            exclusions = [exclusions]

        for pattern in exclusions:
            if fnmatch.fnmatch(rel_path, pattern):
                return False

        return True

    def _get_severity(self, rule: dict) -> AuditSeverity:
        """Parses enforcement level string to Enum."""
        val = rule.get("enforcement", "warn").upper()
        if val == "WARN":
            val = "WARNING"
        try:
            return AuditSeverity[val]
        except KeyError:
            return AuditSeverity.WARNING

    # ID: 20cebb25-123b-40d9-999f-4d849eba4228
    def execute(self) -> list[AuditFinding]:
        """Verifies that Python modules adhere to documented style conventions."""
        findings = []

        # Dispatcher for specific AST checks based on Rule ID
        if "style.docstrings_public_apis" in self.style_rules:
            rule = self.style_rules["style.docstrings_public_apis"]
            findings.extend(self._check_public_docstrings(rule))

        # Other style rules (linter, formatter, import_order) are usually
        # enforced by external tools (Ruff/Black) invoked by other checkers
        # or CI steps. We only implement AST logic here.

        return findings

    def _check_public_docstrings(self, rule: dict) -> list[AuditFinding]:
        """
        Enforces that all public modules, classes, and functions have docstrings.
        """
        findings = []
        severity = self._get_severity(rule)

        for file_path in self.context.python_files:
            if not self._is_file_in_scope(file_path, rule):
                continue

            try:
                content = file_path.read_text(encoding="utf-8")
                tree = ast.parse(content, filename=str(file_path))
                rel_path = str(file_path.relative_to(self.repo_root))

                # 1. Module Docstring
                if not ast.get_docstring(tree):
                    findings.append(
                        AuditFinding(
                            check_id=rule["id"],
                            severity=severity,
                            message="Missing required module-level docstring.",
                            file_path=rel_path,
                            line_number=1,
                        )
                    )

                # 2. Public Symbol Docstrings
                for node in ast.walk(tree):
                    if isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        # Skip private symbols
                        if node.name.startswith("_"):
                            continue

                        # Skip nested classes/functions (simplification)
                        # Checking node.col_offset > 0 is a rough heuristic for nesting
                        # or we could track parent in traversal.
                        # For now, strict enforcement on all public symbols is safer.

                        if not ast.get_docstring(node):
                            findings.append(
                                AuditFinding(
                                    check_id=rule["id"],
                                    severity=severity,
                                    message=f"Public API '{node.name}' is missing a docstring.",
                                    file_path=rel_path,
                                    line_number=node.lineno,
                                )
                            )
            except Exception as e:
                logger.debug("Style check failed for %s: %s", file_path, e)

        return findings
