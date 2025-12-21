# src/mind/governance/checks/dependency_injection_check.py
"""
A constitutional audit check to enforce the Dependency Injection (DI) policy.
Aligns with RULES-STRUCTURE.yaml v2.0 (Flat Rules Array).

Ref: .intent/charter/standards/architecture/dependency_injection.json
"""

from __future__ import annotations

import ast
from collections.abc import Iterable
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: no-direct-instantiation-enforcement
# ID: d377a79c-e5e1-49e8-8b3f-1715689ac305
class NoDirectInstantiationEnforcement(EnforcementMethod):
    """
    Finds direct instantiations of major services.
    Services must be injected via constructors or factories.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: c1a54863-b617-474a-a922-313439d8c96b
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        forbidden_calls: set[str] = set(rule_data.get("forbidden_instantiations", []))
        if not forbidden_calls:
            return findings

        scope: list[str] = rule_data.get("scope", [])
        exclusions: list[str] = rule_data.get("exclusions", [])

        for file_path in self._get_files_in_scope(context, scope, exclusions):
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                        if node.func.id in forbidden_calls:
                            findings.append(
                                self._create_finding(
                                    message=f"Direct instantiation of '{node.func.id}' is forbidden. Inject via constructor.",
                                    file_path=str(
                                        file_path.relative_to(context.repo_path)
                                    ),
                                    line_number=node.lineno,
                                )
                            )
            except (SyntaxError, OSError) as exc:
                logger.debug("Skipping DI scan for %s: %s", file_path, exc)

        return findings

    def _get_files_in_scope(
        self, context: AuditorContext, scope: Iterable[str], exclusions: Iterable[str]
    ) -> list[Path]:
        """Helper to get all files matching the scope and exclusion globs."""
        scope_patterns = list(scope or [])
        exclusion_patterns = list(exclusions or [])

        if not scope_patterns:
            return []

        files: set[Path] = set()
        for glob_pattern in scope_patterns:
            for file_path in context.repo_path.glob(glob_pattern):
                if not file_path.is_file():
                    continue
                # Check exclusions
                if any(file_path.match(ex) for ex in exclusion_patterns):
                    continue
                files.add(file_path)

        return list(files)


# ID: no-global-session-import-enforcement
# ID: e509dc06-fc38-459d-801c-c0cf8fa5f49c
class NoGlobalSessionImportEnforcement(EnforcementMethod):
    """
    Finds direct imports of forbidden functions.
    Database sessions must be injected, not imported globally.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 61a833e8-f6aa-4b3f-a72e-24cf2321307a
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        forbidden_imports: set[str] = set(rule_data.get("forbidden_imports", []))
        if not forbidden_imports:
            return findings

        scope: list[str] = rule_data.get("scope", [])
        exclusions: list[str] = rule_data.get("exclusions", [])

        for file_path in self._get_files_in_scope(context, scope, exclusions):
            try:
                content = file_path.read_text("utf-8")
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    # Check 'from module import name'
                    if isinstance(node, ast.ImportFrom) and node.module:
                        for alias in node.names:
                            full_import = f"{node.module}.{alias.name}"
                            if full_import in forbidden_imports:
                                findings.append(
                                    self._create_finding(
                                        message=f"Direct import of '{full_import}' is forbidden. Inject dependency instead.",
                                        file_path=str(
                                            file_path.relative_to(context.repo_path)
                                        ),
                                        line_number=node.lineno,
                                    )
                                )

                    # Check 'import module'
                    elif isinstance(node, ast.Import):
                        for alias in node.names:
                            if alias.name in forbidden_imports:
                                findings.append(
                                    self._create_finding(
                                        message=f"Direct import of '{alias.name}' is forbidden. Inject dependency instead.",
                                        file_path=str(
                                            file_path.relative_to(context.repo_path)
                                        ),
                                        line_number=node.lineno,
                                    )
                                )

            except (SyntaxError, OSError):
                continue

        return findings

    def _get_files_in_scope(
        self, context: AuditorContext, scope: Iterable[str], exclusions: Iterable[str]
    ) -> list[Path]:
        """Helper to get all files matching the scope and exclusion globs."""
        scope_patterns = list(scope or [])
        exclusion_patterns = list(exclusions or [])

        if not scope_patterns:
            return []

        files: set[Path] = set()
        for glob_pattern in scope_patterns:
            for file_path in context.repo_path.glob(glob_pattern):
                if not file_path.is_file():
                    continue
                if any(file_path.match(ex) for ex in exclusion_patterns):
                    continue
                files.add(file_path)

        return list(files)


# ID: 4a175db2-b65c-41a3-ad2e-a65f344f4e62
class DependencyInjectionCheck(RuleEnforcementCheck):
    """
    Enforces architectural DI boundaries.

    Ref: .intent/charter/standards/architecture/dependency_injection.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "di.no_direct_instantiation",
        "di.no_global_session_import",
        "di.constructor_injection_preferred",
    ]

    policy_file: ClassVar = settings.paths.policy("dependency_injection")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        NoDirectInstantiationEnforcement(rule_id="di.no_direct_instantiation"),
        NoGlobalSessionImportEnforcement(rule_id="di.no_global_session_import"),
        # di.constructor_injection_preferred is currently a guideline (warn level)
        # and doesn't have automated enforcement yet
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
