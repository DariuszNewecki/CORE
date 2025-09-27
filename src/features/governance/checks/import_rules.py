# src/features/governance/checks/import_rules.py
"""
A constitutional audit check to enforce architectural import rules as
defined in the source_structure.yaml manifest.
"""
from __future__ import annotations

import ast
from pathlib import Path
from typing import Dict, List, Set

from sqlalchemy import text

from features.governance.audit_context import AuditorContext
from services.repositories.db.engine import get_session
from shared.models import AuditFinding, AuditSeverity


# --- START OF AMENDMENT: Moved from a separate utility to here ---
# This is now the single source of truth for import scanning.
def _scan_imports(file_path: Path, content: str | None = None) -> List[str]:
    """
    Parse a Python file or its content and extract all imported module paths.
    """
    imports = []
    try:
        source = (
            content if content is not None else file_path.read_text(encoding="utf-8")
        )
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(alias.name)
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.append(node.module)

    except Exception:
        # Fail silently; syntax errors will be caught by other checks.
        pass

    return imports


# --- END OF AMENDMENT ---


# ID: 0690cf39-3739-449e-9228-2c7c8526209b
class ImportRulesCheck:
    """
    Ensures that code files only import modules from their allowed domains.
    This check now reads its configuration from the database.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        self.domain_map: Dict[str, str] = {}
        self.import_rules: Dict[str, Set[str]] = {}
        # The data is now loaded asynchronously when execute is called.

    async def _load_rules_from_db(self):
        """Loads domain maps and import rules from the database."""
        # Avoid reloading if already populated
        if self.domain_map:
            return

        async with get_session() as session:
            await session.execute(text("SELECT key FROM core.domains"))

        structure = self.context.source_structure.get("structure", [])
        for domain_info in structure:
            path_str = domain_info.get("path")
            domain_name = domain_info.get("domain")
            if path_str and domain_name:
                full_path = str((self.context.repo_path / path_str).resolve())
                self.domain_map[full_path] = domain_name

        for domain_info in structure:
            domain_name = domain_info.get("domain")
            allowed_imports = domain_info.get("allowed_imports", [])
            if domain_name:
                self.import_rules[domain_name] = set(allowed_imports)

    def _get_domain_for_path(self, file_path: Path) -> str | None:
        """Finds the domain for a given absolute file path."""
        abs_path_str = str(file_path.resolve())
        for domain_path, domain_name in self.domain_map.items():
            if abs_path_str.startswith(domain_path):
                return domain_name
        return None

    # ID: f1a7dedb-d5e4-442d-8957-b7f974778bc5
    async def execute(self) -> List[AuditFinding]:
        """
        Runs the check by scanning all source files and validating their imports.
        """
        await self._load_rules_from_db()
        findings = []
        src_path = self.context.repo_path / "src"

        for file_path in src_path.rglob("*.py"):
            findings.extend(self._check_file_imports(file_path, file_content=None))
        return findings

    # --- START OF AMENDMENT: New method for validation pipeline ---
    # ID: 31287af5-d942-4a1d-b06d-d0570026d035
    async def execute_on_content(
        self, file_path_str: str, file_content: str
    ) -> List[AuditFinding]:
        """
        Runs the import check on a string of content instead of a file on disk.
        """
        await self._load_rules_from_db()
        file_path = self.context.repo_path / file_path_str
        return self._check_file_imports(file_path, file_content)

    # --- END OF AMENDMENT ---

    def _check_file_imports(
        self, file_path: Path, file_content: str | None
    ) -> List[AuditFinding]:
        """Core logic to check imports for a given file path and optional content."""
        findings = []
        file_domain = self._get_domain_for_path(file_path)
        if not file_domain:
            return []

        allowed_imports = self.import_rules.get(file_domain, set())
        imported_modules = _scan_imports(file_path, content=file_content)

        for module_str in imported_modules:
            if not module_str.startswith(
                ("core", "features", "services", "shared", "cli", "api")
            ):
                continue

            top_level_package = module_str.split(".")[0]

            if top_level_package not in allowed_imports:
                findings.append(
                    AuditFinding(
                        check_id="architecture.import_violation",
                        severity=AuditSeverity.ERROR,
                        message=f"Illegal import of '{module_str}' in domain '{file_domain}'. Allowed: {sorted(list(allowed_imports))}",
                        file_path=str(file_path.relative_to(self.context.repo_path)),
                    )
                )
        return findings
