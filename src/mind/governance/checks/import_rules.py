# src/mind/governance/checks/import_rules.py
"""
A constitutional audit check to enforce architectural import rules,
enforcing the 'structural_compliance' rule.
"""

from __future__ import annotations

import ast
from pathlib import Path

from shared.models import AuditFinding, AuditSeverity

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.base_check import BaseCheck


# ID: 0690cf39-3739-449e-9228-2c7c8526209b
class ImportRulesCheck(BaseCheck):
    """
    Ensures that code files only import modules from their allowed domains,
    as defined in the source_structure policy.
    """

    # Fulfills the contract from BaseCheck.
    policy_rule_ids = ["structural_compliance"]

    def __init__(self, context: AuditorContext):
        super().__init__(context)
        self.domain_map: dict[str, str] = {}
        self.import_rules: dict[str, set[str]] = {}
        self._load_rules_from_policy()

    def _load_rules_from_policy(self):
        """Loads domain maps and import rules from the source_structure policy."""
        if self.domain_map:
            return

        structure_policy = self.context.policies.get("source_structure", {})
        structure = structure_policy.get("structure", [])

        for domain_info in structure:
            path_str = domain_info.get("path")
            domain_name = domain_info.get("domain")
            if path_str and domain_name:
                self.domain_map[path_str] = domain_name

            allowed_imports = domain_info.get("allowed_imports", [])
            if domain_name:
                self.import_rules.setdefault(domain_name, set()).update(allowed_imports)

    # --- THIS FUNCTION IS NOW A METHOD OF THE CLASS ---
    def _scan_imports(self, file_path: Path, content: str | None = None) -> list[str]:
        """
        Parse a Python file or its content and extract all imported module paths.
        """
        imports = []
        try:
            source = (
                content
                if content is not None
                else file_path.read_text(encoding="utf-8")
            )
            tree = ast.parse(source)

            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        imports.append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    if node.module:
                        if node.level > 0:
                            path_parts = list(file_path.parent.parts)
                            # Now this line works because 'self' is defined.
                            base_parts = path_parts[len(self.repo_root.parts) :]
                            if node.level > 1:
                                base_parts = base_parts[: -(node.level - 1)]
                            base_import = ".".join(base_parts)
                            imports.append(f"{base_import}.{node.module}")
                        else:
                            imports.append(node.module)
        except Exception:
            pass
        return imports

    def _get_domain_for_path_str(self, file_path_str: str) -> str | None:
        """Finds the domain for a given relative file path string."""
        best_match, best_domain = "", None
        for domain_path_prefix, domain_name in self.domain_map.items():
            if file_path_str.startswith(domain_path_prefix) and len(
                domain_path_prefix
            ) > len(best_match):
                best_match = domain_path_prefix
                best_domain = domain_name
        return best_domain

    # ID: f1a7dedb-d5e4-442d-8957-b7f974778bc5
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check by scanning all source files and validating their imports.
        """
        findings = []
        for file_path in self.src_dir.rglob("*.py"):
            # Call it as a method: self._scan_imports
            findings.extend(self._check_file_imports(file_path, file_content=None))
        return findings

    # ID: 31287af5-d942-4a1d-b06d-d0570026d035
    def execute_on_content(
        self, file_path_str: str, file_content: str
    ) -> list[AuditFinding]:
        """
        Runs the import check on a string of content instead of a file on disk.
        """
        file_path = self.repo_root / file_path_str
        # Call it as a method: self._scan_imports
        return self._check_file_imports(file_path, file_content)

    def _check_file_imports(
        self, file_path: Path, file_content: str | None
    ) -> list[AuditFinding]:
        """Core logic to check imports for a given file path and optional content."""
        findings = []
        file_rel_path_str = str(file_path.relative_to(self.repo_root))
        file_domain = self._get_domain_for_path_str(file_rel_path_str)
        if not file_domain:
            return []

        allowed_imports = self.import_rules.get(file_domain, set()).copy()
        allowed_imports.add(file_domain)

        # Call it as a method: self._scan_imports
        imported_modules = self._scan_imports(file_path, content=file_content)

        for module_str in imported_modules:
            # Reconstruct a path-like string to check the domain of the imported module
            imported_module_as_path = module_str.replace(".", "/")
            if self._get_domain_for_path_str(imported_module_as_path) == file_domain:
                continue

            imported_domain = module_str.split(".")[0]
            if imported_domain not in allowed_imports:
                findings.append(
                    AuditFinding(
                        check_id="structural_compliance.import_violation",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Illegal import of '{module_str}' in domain '{file_domain}'. "
                            f"Allowed domains: {sorted(list(allowed_imports))}"
                        ),
                        file_path=file_rel_path_str,
                    )
                )
        return findings
