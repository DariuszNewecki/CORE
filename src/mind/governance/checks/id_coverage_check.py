# src/mind/governance/checks/id_coverage_check.py
"""
Ensures public symbols in Governance Domains (Features, Core) have '# ID: <uuid>' tags.
Respects architectural exemptions for Infrastructure, CLI, and API layers.

Ref: .intent/charter/standards/operations/operations.json
Ref: .intent/charter/standards/architecture/layer_contracts.json
"""

from __future__ import annotations

import ast
from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.ast_utility import find_symbol_id_and_def_line
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

OPERATIONS_POLICY = Path(".intent/charter/standards/operations/operations.json")


# ID: id-coverage-enforcement
# ID: b55754b7-5f08-47a5-9ea8-e446f03a24d7
class IdCoverageEnforcement(EnforcementMethod):
    """
    Verifies that public symbols in business logic layers have ID tags.
    Respects architectural layer exemptions.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: dfd31a5e-d186-49f2-8ce7-d0c72a9bae9c
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        for file_path in context.src_dir.rglob("*.py"):
            # Normalize path for checking
            rel_path = str(file_path.relative_to(context.repo_path)).replace("\\", "/")

            # Optimization: Skip test files immediately
            if "tests/" in rel_path or "test_" in file_path.name:
                continue

            try:
                content = file_path.read_text("utf-8")
                source_lines = content.splitlines()
                tree = ast.parse(content, filename=str(file_path))

                for node in ast.walk(tree):
                    # Check Functions and Classes
                    if not isinstance(
                        node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
                    ):
                        continue

                    # 1. Private Symbol Exemption (Standard Python Convention)
                    if node.name.startswith("_"):
                        continue

                    # 2. Architectural Layer Exemptions (Ref: layer_contracts.yaml)
                    if self._is_exempt(rel_path, node.name):
                        continue

                    # 3. Check for ID
                    id_result = find_symbol_id_and_def_line(node, source_lines)

                    if not id_result.has_id:
                        findings.append(
                            self._create_finding(
                                message=(
                                    f"Public symbol '{node.name}' in business layer requires '# ID: <uuid>'. "
                                    "Run `core-admin fix ids`."
                                ),
                                file_path=rel_path,
                                line_number=id_result.definition_line_num,
                            )
                        )

            except Exception as exc:
                logger.debug("Skipping ID scan for %s: %s", file_path, exc)
                continue

        return findings

    def _is_exempt(self, file_path: str, symbol_name: str) -> bool:
        """
        Determines if a symbol is exempt from ID requirements based on
        standard_architecture_layer_contracts.
        """
        # 1. Infrastructure Layer (Service APIs)
        if "shared/infrastructure" in file_path:
            return True

        # 2. Provider Implementations (Interface Contracts)
        if "/providers/" in file_path:
            return True

        # 3. CLI Entry Points (Framework Managed)
        if "body/cli" in file_path:
            return True

        # 4. HTTP API Endpoints (Framework Managed)
        if "src/api" in file_path:
            return True

        # 5. Magic Methods (Python Runtime)
        if symbol_name.startswith("__") and symbol_name.endswith("__"):
            return True

        # 6. Registry Dispatched Methods (Contract Implementation)
        # e.g., BaseCheck.execute, ActionHandler.execute
        if symbol_name == "execute" and (
            "checks/" in file_path or "actions/" in file_path
        ):
            return True

        # 7. Visitor Pattern (AST Walkers)
        if symbol_name.startswith("visit_"):
            return True

        return False


# ID: f69a1a2e-26cd-4cc2-8fdc-7f18e0e77d0c
class IdCoverageCheck(RuleEnforcementCheck):
    """
    Ensures public symbols in Governance Domains (Features, Core) have '# ID: <uuid>' tags.
    Respects architectural exemptions for Infrastructure, CLI, and API layers.

    Ref: .intent/charter/standards/operations/operations.json
    Ref: .intent/charter/standards/architecture/layer_contracts.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "linkage.assign_ids",
    ]

    policy_file: ClassVar[Path] = OPERATIONS_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        IdCoverageEnforcement(rule_id="linkage.assign_ids"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
