# src/features/governance/checks/file_checks.py
"""
Audits file existence and orphan detection for constitutional governance files.
"""

from __future__ import annotations

from typing import List, Set

from shared.config import settings
from shared.models import AuditFinding, AuditSeverity
from shared.utils.constitutional_parser import get_all_constitutional_paths

from features.governance.checks.base_check import BaseCheck

# Files that are allowed to exist but are not indexed in meta.yaml
KNOWN_UNINDEXED_FILES = {
    ".intent/charter/constitution/approvers.yaml.example",
    # Keys should not be checked into git, but if they are, don't flag as orphan
    ".intent/keys/private.key",
}

# --- START OF AMENDMENT: Define Deprecated Files ---
# These files are now constitutionally forbidden as the database is the SSOT.
DEPRECATED_KNOWLEDGE_FILES = [
    ".intent/knowledge/cli_registry.yaml",
    ".intent/knowledge/resource_manifest.yaml",
    ".intent/knowledge/cognitive_roles.yaml",
]
# --- END OF AMENDMENT ---


# ID: 37b5ae2f-c3c2-4db4-9677-f16fd788c908
class FileChecks(BaseCheck):
    """Container for file-based constitutional checks."""

    # ID: 56481071-3a0c-437d-ba57-533bc03d9ed6
    def execute(self) -> List[AuditFinding]:
        """Runs all file-related checks."""
        meta_content = settings._meta_config

        required_files = get_all_constitutional_paths(meta_content, self.intent_path)

        findings = self._check_required_files(required_files)
        findings.extend(self._check_for_orphaned_intent_files(required_files))
        # --- START OF AMENDMENT: Add the new check to the execution flow ---
        findings.extend(self._check_for_deprecated_files())
        # --- END OF AMENDMENT ---
        return findings

    # --- START OF AMENDMENT: Add the new check method ---
    def _check_for_deprecated_files(self) -> List[AuditFinding]:
        """Verify that files constitutionally replaced by the database do not exist."""
        findings: List[AuditFinding] = []
        for file_rel_path in DEPRECATED_KNOWLEDGE_FILES:
            full_path = self.repo_root / file_rel_path
            if full_path.exists():
                findings.append(
                    AuditFinding(
                        check_id="file.ssot.deprecated_exists",
                        severity=AuditSeverity.ERROR,
                        message=f"Deprecated knowledge file '{file_rel_path}' exists. The database is now the single source of truth.",
                        file_path=file_rel_path,
                    )
                )
        return findings

    # --- END OF AMENDMENT ---

    def _check_required_files(self, required_files: Set[str]) -> List[AuditFinding]:
        """Verify that all files declared in meta.yaml exist on disk."""
        findings: List[AuditFinding] = []

        for file_rel_path in sorted(required_files):
            full_path = self.repo_root / file_rel_path
            if not full_path.exists():
                findings.append(
                    AuditFinding(
                        check_id="file.meta.missing",
                        severity=AuditSeverity.ERROR,
                        message=f"Missing constitutionally-required file declared in meta.yaml: '{file_rel_path}'",
                        file_path=file_rel_path,
                    )
                )
        return findings

    def _check_for_orphaned_intent_files(
        self, declared_files: Set[str]
    ) -> List[AuditFinding]:
        """Find .intent files not referenced in meta.yaml."""
        findings: List[AuditFinding] = []

        # Add a README to proposals, which is fine to be un-indexed
        all_known_files = declared_files.union(KNOWN_UNINDEXED_FILES)
        if (self.intent_path / "proposals/README.md").exists():
            all_known_files.add(".intent/proposals/README.md")

        physical_files: Set[str] = {
            str(p.relative_to(self.repo_root)).replace("\\", "/")
            for p in self.intent_path.rglob("*")
            if p.is_file()
        }

        orphaned_files = sorted(physical_files - all_known_files)

        for orphan in orphaned_files:
            if "prompts" in orphan or "reports" in orphan:
                continue
            findings.append(
                AuditFinding(
                    check_id="file.meta.orphaned",
                    severity=AuditSeverity.WARNING,
                    message=f"Orphaned intent file: '{orphan}' is not a recognized constitutional file. Add it to meta.yaml or remove it.",
                    file_path=orphan,
                )
            )
        return findings
