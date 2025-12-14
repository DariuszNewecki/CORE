# src/mind/governance/checks/dependency_injection_check.py

"""
A constitutional audit check to enforce the Dependency Injection (DI) policy.
Aligns with RULES-STRUCTURE.yaml v2.0 (Flat Rules Array).
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 4a175db2-b65c-41a3-ad2e-a65f344f4e62
class DependencyInjectionCheck(BaseCheck):
    """
    Enforces architectural DI boundaries.
    Loads rules from 'dependency_injection' standard (preferred) or 'code_standards'.
    """

    policy_rule_ids = [
        "di.no_direct_instantiation",
        "di.no_global_session_import",
        "di.constructor_injection_preferred",
    ]

    def __init__(self, context: AuditorContext) -> None:
        """
        Initializes the check using v2.0 flat rule structure lookup.
        """
        super().__init__(context)

        # 1. Try to load from the dedicated architecture standard (SSOT)
        # Ref: .intent/charter/standards/architecture/dependency_injection.yaml
        policy_data = self.context.policies.get("dependency_injection", {})

        # 2. Fallback to code_standards if dedicated file not found
        if not policy_data:
            policy_data = self.context.policies.get("code_standards", {})

        # 3. Parse Flat Rules Array (Big Boys Pattern)
        raw_rules = policy_data.get("rules", [])

        # Filter for the rules this check cares about
        self.rules_by_id = {}
        for rule in raw_rules:
            if rule.get("id") in self.policy_rule_ids:
                self.rules_by_id[rule["id"]] = rule

        if not self.rules_by_id:
            logger.warning(
                "DI Check: No relevant rules found in loaded policies. "
                "Ensure 'dependency_injection.yaml' is loaded and follows RULES-STRUCTURE.yaml."
            )

    # ID: a407a678-5515-46f8-a838-20e7c85086f6
    def execute(self) -> list[AuditFinding]:
        """Runs the DI check by scanning source files for policy violations."""
        findings: list[AuditFinding] = []

        if "di.no_direct_instantiation" in self.rules_by_id:
            rule = self.rules_by_id["di.no_direct_instantiation"]
            findings.extend(self._check_forbidden_instantiations(rule))

        if "di.no_global_session_import" in self.rules_by_id:
            rule = self.rules_by_id["di.no_global_session_import"]
            findings.extend(self._check_forbidden_imports(rule))

        # Constructor injection check is currently a placeholder in logic,
        # but correctly wired for future implementation.

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
                                    check_id=rule.get("id"),
                                    severity=AuditSeverity.ERROR,
                                    message=f"Direct instantiation of '{node.func.id}' is forbidden. Inject via constructor.",
                                    file_path=str(
                                        file_path.relative_to(self.repo_root)
                                    ),
                                    line_number=node.lineno,
                                    context={"category": "architectural"},
                                )
                            )
            except (SyntaxError, OSError) as exc:
                logger.debug("Skipping DI scan for %s: %s", file_path, exc)

        return findings

    def _check_forbidden_imports(self, rule: dict[str, Any]) -> list[AuditFinding]:
        """Finds direct imports of forbidden functions."""
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
                    # Check 'from module import name'
                    if isinstance(node, ast.ImportFrom) and node.module:
                        # Construct full import path being accessed
                        for alias in node.names:
                            full_import = f"{node.module}.{alias.name}"
                            if full_import in forbidden_imports:
                                findings.append(
                                    self._create_import_finding(
                                        rule, file_path, node, full_import
                                    )
                                )

                    # Check 'import module'
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in forbidden_imports:
                                findings.append(
                                    self._create_import_finding(
                                        rule, file_path, node, alias.name
                                    )
                                )

            except (SyntaxError, OSError):
                continue

        return findings

    def _create_import_finding(self, rule, file_path, node, import_name):
        return AuditFinding(
            check_id=rule.get("id"),
            severity=AuditSeverity.ERROR,
            message=f"Direct import of '{import_name}' is forbidden. Inject dependency instead.",
            file_path=str(file_path.relative_to(self.repo_root)),
            line_number=node.lineno,
            context={"category": "architectural"},
        )

    def _get_files_in_scope(
        self, scope: Iterable[str], exclusions: Iterable[str]
    ) -> list[Path]:
        """Helper to get all files matching the scope and exclusion globs."""
        scope_patterns = list(scope or [])
        exclusion_patterns = list(exclusions or [])

        if not scope_patterns:
            return []

        files: set[Path] = set()
        for glob_pattern in scope_patterns:
            # Handle standard glob patterns
            for file_path in self.repo_root.glob(glob_pattern):
                if not file_path.is_file():
                    continue
                # Check exclusions
                if any(file_path.match(ex) for ex in exclusion_patterns):
                    continue
                files.add(file_path)

        return list(files)
