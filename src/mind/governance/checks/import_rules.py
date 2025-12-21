# src/mind/governance/checks/import_rules.py
"""
Enforces dependency injection and layer boundary rules from Constitution.

Constitutional Rules Enforced:
- di.no_global_session_import: No direct global session imports in features/services
- Mind/Body/Will layer separation
- Architectural domain boundaries per project_structure.json
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import ClassVar

import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 0690cf39-3739-449e-9228-2c7c8526209b
class ImportRulesCheck(BaseCheck):
    """
    Ensures that code files only import modules from their allowed architectural domains.

    Enforces constitutional rules:
    - di.no_global_session_import (error)
    - Mind/Body/Will layer separation boundaries
    - Architectural domain boundaries per project_structure.json

    Ref: .intent/charter/standards/architecture/dependency_injection.json
    Ref: .intent/charter/constitution/boundaries.json
    Ref: .intent/mind/knowledge/project_structure.json
    """

    # Constitutional rule IDs this check enforces
    policy_rule_ids: ClassVar[list[str]] = [
        "di.no_global_session_import",
        "structural_compliance.import_violation",
    ]

    def __init__(self, context: AuditorContext):
        super().__init__(context)
        self.domain_map: dict[str, str] = {}  # path_prefix -> domain_name
        self.allowed_imports: dict[str, set[str]] = (
            {}
        )  # domain_name -> set(allowed_domains)
        self._load_rules_from_ssot()

    def _load_rules_from_ssot(self):
        """Loads architectural domains from project_structure (JSON first, then YAML)."""
        json_struct = self.context.mind_path / "knowledge/project_structure.json"
        yaml_struct = self.context.mind_path / "knowledge/project_structure.yaml"

        data = None
        if json_struct.exists():
            try:
                data = json.loads(json_struct.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error("Failed to parse project_structure.json: %s", e)

        if data is None and yaml_struct.exists():
            try:
                data = yaml.safe_load(yaml_struct.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error("Failed to parse project_structure.yaml: %s", e)

        if not data:
            logger.warning(
                "Project structure SSOT missing. Import rules cannot be enforced."
            )
            return

        try:
            domains = data.get("architectural_domains", [])
            for d in domains:
                path = d.get("path")  # e.g., "src/features"
                name = d.get("domain")  # e.g., "features"
                allowed = d.get("allowed_imports", [])

                if path and name:
                    self.domain_map[path] = name
                    # A domain can always import from itself
                    self.allowed_imports[name] = set(allowed) | {name}
        except Exception as e:
            logger.error("Data error in project structure: %s", e)

    # ID: f1a7dedb-d5e4-442d-8957-b7f974778bc5
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by scanning all source files.
        Standardized to 'execute' for Atomic Action compliance.
        """
        findings = []
        for file_path in self.src_dir.rglob("*.py"):
            findings.extend(self._check_file_imports(file_path))
        return findings

    def _check_file_imports(self, file_path: Path) -> list[AuditFinding]:
        """Validates imports for a single file."""
        findings = []

        try:
            rel_path = file_path.relative_to(self.repo_root)
            rel_path_str = str(rel_path).replace("\\", "/")
        except ValueError:
            return []

        file_domain = self._get_domain_for_path(rel_path_str)
        if not file_domain:
            return []

        allowed = self.allowed_imports.get(file_domain, set())
        imports = self._scan_imports(file_path)

        for module in imports:
            # 1. Check for prohibited global session import
            if self._is_global_session_import(module, file_domain):
                findings.append(
                    AuditFinding(
                        check_id="di.no_global_session_import",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Illegal import: '{module}' violates di.no_global_session_import. "
                            f"Features and services MUST NOT directly import global session."
                        ),
                        file_path=rel_path_str,
                        line_number=1,
                        context={
                            "source_domain": file_domain,
                            "imported_module": module,
                        },
                    )
                )
                continue

            # 2. Check for domain boundary violations
            root_module = module.split(".")[0]
            target_domain = None

            if root_module in self.allowed_imports:
                target_domain = root_module

            if target_domain and target_domain not in allowed:
                findings.append(
                    AuditFinding(
                        check_id="structural_compliance.import_violation",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Illegal import: Domain '{file_domain}' cannot import '{module}' "
                            f"(Domain: '{target_domain}'). Allowed: {sorted(list(allowed))}."
                        ),
                        file_path=rel_path_str,
                        line_number=1,
                        context={
                            "source_domain": file_domain,
                            "target_domain": target_domain,
                            "imported_module": module,
                        },
                    )
                )

        return findings

    def _is_global_session_import(self, module: str, file_domain: str) -> bool:
        """Detect if this is a prohibited global session import."""
        if file_domain not in ("features", "services"):
            return False

        prohibited_patterns = [
            "shared.database.get_session",
            "database.get_session",
            "core.database.get_session",
            "shared.infrastructure.database.session_manager.get_session",
        ]
        return any(module.startswith(pattern) for pattern in prohibited_patterns)

    def _scan_imports(self, file_path: Path) -> list[str]:
        """Extracts all imported module paths from a file."""
        imports = []
        try:
            content = file_path.read_text(encoding="utf-8")
            tree = ast.parse(content, filename=str(file_path))

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module and node.level == 0:
                        imports.append(node.module)
        except Exception as e:
            logger.debug("Failed to parse imports for %s: %s", file_path, e)

        return imports

    def _get_domain_for_path(self, path_str: str) -> str | None:
        """Matches file path to longest specific domain path."""
        best_match = None
        longest_prefix = 0

        for prefix, domain in self.domain_map.items():
            if path_str.startswith(prefix):
                if len(prefix) > longest_prefix:
                    longest_prefix = len(prefix)
                    best_match = domain

        return best_match
