# src/mind/governance/checks/import_rules.py
"""
Enforces structural_compliance: Code must obey architectural layer boundaries.
defined in project_structure.yaml.
"""

from __future__ import annotations

import ast
from pathlib import Path

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
    Ref: .intent/mind/knowledge/project_structure.yaml
    """

    policy_rule_ids = ["structural_compliance"]

    def __init__(self, context: AuditorContext):
        super().__init__(context)
        self.domain_map: dict[str, str] = {}  # path_prefix -> domain_name
        self.allowed_imports: dict[
            str, set[str]
        ] = {}  # domain_name -> set(allowed_domains)
        self._load_rules_from_ssot()

    def _load_rules_from_ssot(self):
        """Loads architectural domains from project_structure.yaml."""
        struct_path = self.context.mind_path / "knowledge/project_structure.yaml"

        if not struct_path.exists():
            logger.warning(
                "project_structure.yaml missing. Import rules cannot be enforced."
            )
            return

        try:
            data = yaml.safe_load(struct_path.read_text(encoding="utf-8"))
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
            logger.error("Failed to load import rules: %s", e)

    # ID: f1a7dedb-d5e4-442d-8957-b7f974778bc5
    def execute(self) -> list[AuditFinding]:
        """Runs the check by scanning all source files."""
        findings = []
        # Use src_dir for scanning
        for file_path in self.src_dir.rglob("*.py"):
            findings.extend(self._check_file_imports(file_path))
        return findings

    def _check_file_imports(self, file_path: Path) -> list[AuditFinding]:
        """Validates imports for a single file."""
        findings = []

        # 1. Determine Domain of Current File
        # We need relative path from repo root to match "src/..." keys
        try:
            rel_path = file_path.relative_to(self.repo_root)
            rel_path_str = str(rel_path).replace("\\", "/")  # Normalize separators
        except ValueError:
            return []  # Outside repo?

        file_domain = self._get_domain_for_path(rel_path_str)
        if not file_domain:
            # File is not in a governed domain (e.g. scripts root), skip checks
            return []

        allowed = self.allowed_imports.get(file_domain, set())

        # 2. Scan Imports
        imports = self._scan_imports(file_path)

        # 3. Validate
        for module in imports:
            # Determine domain of the imported module
            # Logic: If 'features.x', domain is 'features'.
            # If 'shared.logger', domain is 'shared'.
            root_module = module.split(".")[0]

            # Identify if this root_module corresponds to a known internal domain
            # We map back: find if any domain name matches this root_module
            # This relies on the convention that src/<name> maps to module <name>
            target_domain = None

            # Check if this module is one of our managed domains
            if root_module in self.allowed_imports:
                target_domain = root_module

            # If it's 3rd party (e.g., 'os', 'fastapi'), target_domain is None.
            # We only police internal boundaries.
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
                        line_number=1,  # Todo: pass line numbers from scan
                        context={
                            "source_domain": file_domain,
                            "target_domain": target_domain,
                            "imported_module": module,
                        },
                    )
                )

        return findings

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
                    if node.module:
                        if node.level == 0:
                            # Absolute import: from shared.logger import ...
                            imports.append(node.module)
                        else:
                            # Relative import: from ..shared import ...
                            # We construct the absolute path to check boundaries
                            # Simplification: Treat relative imports as "Internal to Domain" usually,
                            # but strictly we should resolve them.
                            # For now, we skip verifying relative imports as they usually imply
                            # staying within the same package tree.
                            pass
        except Exception as e:
            logger.debug("Failed to parse imports for %s: %s", file_path, e)

        return imports

    def _get_domain_for_path(self, path_str: str) -> str | None:
        """Matches file path to longest specific domain path."""
        # e.g., src/features/auth/login.py -> matches src/features -> 'features'
        best_match = None
        longest_prefix = 0

        for prefix, domain in self.domain_map.items():
            if path_str.startswith(prefix):
                if len(prefix) > longest_prefix:
                    longest_prefix = len(prefix)
                    best_match = domain

        return best_match
