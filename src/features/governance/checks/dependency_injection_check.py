# src/features/governance/checks/dependency_injection_check.py
"""
A constitutional audit check to enforce the Dependency Injection (DI) policy.
"""

from __future__ import annotations

import ast
from pathlib import Path

from features.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 7cdf99c0-ebe2-4a36-9a6f-9d32dd6ee1db
class DependencyInjectionCheck(BaseCheck):
    """
    Ensures that services and features do not directly instantiate their dependencies,
    and do not use forbidden global imports like `get_session`.
    """

    def __init__(self, context):
        super().__init__(context)
        self.policy = self.context.policies.get("dependency_injection_policy", {})

    # ID: b854f7a7-fe4f-4ec6-8b9d-04bd32c98102
    def execute(self) -> list[AuditFinding]:
        """Runs the DI check by scanning source files for policy violations."""
        findings = []
        rules = self.policy.get("rules", [])
        if not rules:
            return findings

        for rule in rules:
            if rule.get("id") == "di.no_direct_instantiation":
                findings.extend(self._check_forbidden_instantiations(rule))
            elif rule.get("id") == "di.no_global_session_import":
                findings.extend(self._check_forbidden_imports(rule))

        return findings

    def _check_forbidden_instantiations(self, rule: dict) -> list[AuditFinding]:
        """Finds direct instantiations of major services."""
        findings = []
        forbidden_calls = set(rule.get("forbidden_instantiations", []))
        scope = rule.get("scope", [])
        exclusions = rule.get("exclusions", [])

        for file_path in self._get_files_in_scope(scope, exclusions):
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in forbidden_calls:
                            findings.append(
                                AuditFinding(
                                    check_id=rule["id"],
                                    severity=AuditSeverity.ERROR,
                                    message=f"Direct instantiation of '{node.func.id}' is forbidden. Inject it via the constructor.",
                                    file_path=str(
                                        file_path.relative_to(self.repo_root)
                                    ),
                                    line_number=node.lineno,
                                    category="architectural",  # <-- ADD THIS LINE
                                )
                            )
            except Exception:
                continue
        return findings

    def _check_forbidden_imports(self, rule: dict) -> list[AuditFinding]:
        """Finds direct imports of forbidden functions like get_session."""
        findings = []
        forbidden_imports = set(rule.get("forbidden_imports", []))
        scope = rule.get("scope", [])
        exclusions = rule.get("exclusions", [])

        for file_path in self._get_files_in_scope(scope, exclusions):
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if (
                        isinstance(node, ast.ImportFrom)
                        and node.module in forbidden_imports
                    ):
                        findings.append(
                            AuditFinding(
                                check_id=rule["id"],
                                severity=AuditSeverity.ERROR,
                                message=f"Direct import of '{node.module}' is forbidden. Inject the dependency instead.",
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=node.lineno,
                                category="architectural",  # <-- ADD THIS LINE
                            )
                        )
            except Exception:
                continue
        return findings

    def _get_files_in_scope(
        self, scope: list[str], exclusions: list[str]
    ) -> list[Path]:
        """Helper to get all files matching the scope and exclusion globs."""
        files = []
        for glob_pattern in scope:
            for file_path in self.repo_root.glob(glob_pattern):
                if file_path.is_file() and not any(
                    file_path.match(ex) for ex in exclusions
                ):
                    files.append(file_path)
        return list(set(files))
