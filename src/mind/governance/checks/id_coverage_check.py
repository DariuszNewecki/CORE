# src/mind/governance/checks/id_coverage_check.py
"""
Enforces the requirement for Capability IDs on public business logic.
Respects architectural exemptions defined in layer_contracts.yaml.
"""

from __future__ import annotations

import ast

from mind.governance.checks.base_check import BaseCheck
from shared.ast_utility import find_symbol_id_and_def_line
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 3501ed8c-8366-4ad7-9ab4-7dcf4c045c70
class IdCoverageCheck(BaseCheck):
    """
    Ensures public symbols in Governance Domains (Features, Core) have '# ID: <uuid>' tags.
    Respects architectural exemptions for Infrastructure, CLI, and API layers.
    Ref: standard_architecture_layer_contracts
    """

    policy_rule_ids = [
        "linkage.assign_ids",
        "symbols.public_capability_id_and_docstring",
        "architecture.feature_capabilities_required",
    ]

    # ID: f69a1a2e-26cd-4cc2-8fdc-7f18e0e77d0c
    def execute(self) -> list[AuditFinding]:
        findings = []

        for file_path in self.src_dir.rglob("*.py"):
            # Normalize path for checking
            rel_path = str(file_path.relative_to(self.repo_root)).replace("\\", "/")

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
                            AuditFinding(
                                check_id="linkage.assign_ids",
                                severity=AuditSeverity.ERROR,
                                message=(
                                    f"Public symbol '{node.name}' in business layer requires '# ID: <uuid>'. "
                                    "Run `core-admin fix ids`."
                                ),
                                file_path=rel_path,
                                line_number=id_result.definition_line_num,
                                context={
                                    "symbol": node.name,
                                    "layer": self._get_layer_name(rel_path),
                                },
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

    def _get_layer_name(self, file_path: str) -> str:
        """Helper for context reporting."""
        if "features/" in file_path:
            return "Features"
        if "core/" in file_path:
            return "Core Orchestration"
        if "services/" in file_path:
            return "Domain Services"
        return "Unknown Layer"
