# src/features/governance/checks/import_rules.py
"""
A constitutional audit check to enforce architectural import rules as
defined in the source_structure.yaml manifest.
"""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Set

from features.governance.audit_context import AuditorContext
from shared.models import AuditFinding, AuditSeverity
from shared.utils.import_scanner import scan_imports_for_file


# ID: 0690cf39-3739-449e-9228-2c7c8526209b
class ImportRulesCheck:
    """
    Ensures that code files only import modules from their allowed domains.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        self.domain_map = self._build_domain_map()
        self.import_rules = self._build_import_rules()

    def _build_domain_map(self) -> Dict[str, str]:
        """Creates a map from directory paths to domain names."""
        domain_map = {}
        structure = self.context.source_structure.get("structure", [])
        for domain_info in structure:
            path_str = domain_info.get("path")
            domain_name = domain_info.get("domain")
            if path_str and domain_name:
                full_path = str((self.context.repo_path / path_str).resolve())
                domain_map[full_path] = domain_name
        return domain_map

    def _build_import_rules(self) -> Dict[str, Set[str]]:
        """Creates a map from a domain to the set of domains it's allowed to import."""
        rules = {}
        structure = self.context.source_structure.get("structure", [])
        for domain_info in structure:
            domain_name = domain_info.get("domain")
            allowed_imports = domain_info.get("allowed_imports", [])
            if domain_name:
                rules[domain_name] = set(allowed_imports)
        return rules

    def _get_domain_for_path(self, file_path: Path) -> str | None:
        """Finds the domain for a given absolute file path."""
        abs_path_str = str(file_path.resolve())
        for domain_path, domain_name in self.domain_map.items():
            if abs_path_str.startswith(domain_path):
                return domain_name
        return None

    # ID: f1a7dedb-d5e4-442d-8957-b7f974778bc5
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check by scanning all source files and validating their imports.
        """
        findings = []
        src_path = self.context.repo_path / "src"

        for file_path in src_path.rglob("*.py"):
            file_domain = self._get_domain_for_path(file_path)
            if not file_domain:
                continue

            allowed_imports = self.import_rules.get(file_domain, set())
            imported_modules = scan_imports_for_file(file_path)

            for module_str in imported_modules:
                # We only care about internal imports for this check
                if not module_str.startswith(
                    ("core", "features", "services", "shared", "cli", "api")
                ):
                    continue

                # A simple heuristic: check the top-level package
                top_level_package = module_str.split(".")[0]

                if top_level_package not in allowed_imports:
                    findings.append(
                        AuditFinding(
                            check_id="architecture.import_violation",
                            severity=AuditSeverity.ERROR,
                            message=f"Illegal import of '{module_str}' in domain '{file_domain}'. Allowed: {sorted(list(allowed_imports))}",
                            file_path=str(
                                file_path.relative_to(self.context.repo_path)
                            ),
                        )
                    )
        return findings
