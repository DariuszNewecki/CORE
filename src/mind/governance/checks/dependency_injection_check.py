# src/mind/governance/checks/dependency_injection_check.py
"""
A constitutional audit check to enforce the Dependency Injection (DI) policy.

This check is responsible for enforcing all DI-related policy rules
from charter/policies/code_standards.yaml.
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck

logger = getLogger(__name__)


# ID: 68fa7a18-3591-46ad-9470-0a0bb8685491
class DependencyInjectionCheck(BaseCheck):
    """
    Ensures that services and features do not directly instantiate their dependencies,
    do not use forbidden global imports, and prefer constructor injection.
    """

    # Fulfills the contract from BaseCheck, now covering ALL DI rules.
    policy_rule_ids = [
        "di.no_direct_instantiation",
        "di.no_global_session_import",
        "di.constructor_injection_preferred",
    ]

    def __init__(self, context: AuditorContext) -> None:
        super().__init__(context)
        code_standards_policy: dict[str, Any] = self.context.policies.get(
            "code_standards", {}
        )
        self.policy: list[dict[str, Any]] = code_standards_policy.get(
            "dependency_injection", []
        )
        # Create a quick lookup map for rules by their ID for efficiency
        self.rules_by_id = {rule.get("id"): rule for rule in self.policy}

    # ID: e0b8b3db-959e-4ac1-bc26-a7f3e1b35bc0
    def execute(self) -> list[AuditFinding]:
        """Runs the DI check by scanning source files for policy violations."""
        findings: list[AuditFinding] = []

        # More robustly check if a specific rule is defined in the policy
        if "di.no_direct_instantiation" in self.rules_by_id:
            rule = self.rules_by_id["di.no_direct_instantiation"]
            findings.extend(self._check_forbidden_instantiations(rule))

        if "di.no_global_session_import" in self.rules_by_id:
            rule = self.rules_by_id["di.no_global_session_import"]
            findings.extend(self._check_forbidden_imports(rule))

        if "di.constructor_injection_preferred" in self.rules_by_id:
            rule = self.rules_by_id["di.constructor_injection_preferred"]
            findings.extend(self._check_constructor_injection(rule))

        return findings

    def _check_forbidden_instantiations(
        self, rule: dict[str, Any]
    ) -> list[AuditFinding]:
        """Finds direct instantiations of major services."""
        findings: list[AuditFinding] = []
        forbidden_calls: set[str] = set(rule.get("forbidden_instantiations", []))
        if not forbidden_calls:
            return findings

        scope: list[str] = rule.get("scope", [])
        exclusions: list[str] = rule.get("exclusions", [])

        for file_path in self._get_files_in_scope(scope, exclusions):
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in forbidden_calls:
                            findings.append(
                                AuditFinding(
                                    # Use the rule ID directly from the policy
                                    check_id=rule.get("id"),
                                    severity=AuditSeverity.ERROR,
                                    message=(
                                        f"Direct instantiation of '{node.func.id}' is "
                                        "forbidden. Inject it via the constructor."
                                    ),
                                    file_path=str(
                                        file_path.relative_to(self.repo_root)
                                    ),
                                    line_number=node.lineno,
                                    context={"category": "architectural"},
                                )
                            )
            except (SyntaxError, OSError) as exc:
                logger.debug("Skipping DI scan for %s due to error: %s", file_path, exc)
        return findings

    def _check_forbidden_imports(self, rule: dict[str, Any]) -> list[AuditFinding]:
        """Finds direct imports of forbidden functions like get_session."""
        findings: list[AuditFinding] = []
        forbidden_imports: set[str] = set(rule.get("forbidden_imports", []))
        if not forbidden_imports:
            return findings

        scope: list[str] = rule.get("scope", [])
        exclusions: list[str] = rule.get("exclusions", [])

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
                                # Use the rule ID directly from the policy
                                check_id=rule.get("id"),
                                severity=AuditSeverity.ERROR,
                                message=(
                                    f"Direct import of '{node.module}' is forbidden. "
                                    "Inject the dependency instead."
                                ),
                                file_path=str(file_path.relative_to(self.repo_root)),
                                line_number=node.lineno,
                                context={"category": "architectural"},
                            )
                        )
            except (SyntaxError, OSError) as exc:
                logger.debug("Skipping DI scan for %s due to error: %s", file_path, exc)
        return findings

    def _check_constructor_injection(self, rule: dict[str, Any]) -> list[AuditFinding]:
        """
        Verifies that services prefer constructor injection.

        NOTE: This is a complex check to implement fully via static analysis.
        This serves as a placeholder for future enhancement.
        """
        # TODO: Implement AST logic to detect when services are instantiated
        # as attributes outside of the constructor.
        return []

    def _get_files_in_scope(
        self, scope: Iterable[str], exclusions: Iterable[str]
    ) -> list[Path]:
        """Helper to get all files matching the scope and exclusion globs."""
        scope_patterns = list(scope or [])
        exclusion_patterns = list(exclusions or [])
        if not scope_patterns:
            return []

        files: list[Path] = []
        for glob_pattern in scope_patterns:
            for file_path in self.repo_root.glob(glob_pattern):
                if not file_path.is_file():
                    continue
                if any(file_path.match(ex) for ex in exclusion_patterns):
                    continue
                files.append(file_path)

        return list({p.resolve() for p in files})
