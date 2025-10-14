# src/features/governance/checks/file_checks.py
"""
Audits file existence and orphan detection for constitutional governance files.
"""

from __future__ import annotations

from features.governance.checks.base_check import BaseCheck
from shared.config import settings
from shared.models import AuditFinding, AuditSeverity
from shared.utils.constitutional_parser import get_all_constitutional_paths

KNOWN_UNINDEXED_FILES = {
    ".intent/charter/constitution/approvers.yaml.example",
    ".intent/keys/private.key",
}

DEPRECATED_KNOWLEDGE_FILES = [
    ".intent/knowledge/cli_registry.yaml",
    ".intent/knowledge/resource_manifest.yaml",
    ".intent/knowledge/cognitive_roles.yaml",
]


# ID: 37b5ae2f-c3c2-4db4-9677-f16fd788c908
class FileChecks(BaseCheck):
    """Container for file-based constitutional checks."""

    # ID: 56481071-3a0c-437d-ba57-533bc03d9ed6
    def execute(self) -> list[AuditFinding]:
        """Runs all file-related checks."""
        meta_content = settings._meta_config
        required_files = get_all_constitutional_paths(meta_content, self.intent_path)
        findings = self._check_required_files(required_files)
        findings.extend(self._check_for_orphaned_intent_files(required_files))
        findings.extend(self._check_for_deprecated_files())
        return findings

    def _check_for_deprecated_files(self) -> list[AuditFinding]:
        """Verify that files constitutionally replaced by the database do not exist."""
        findings: list[AuditFinding] = []
        for file_rel_path in DEPRECATED_KNOWLEDGE_FILES:
            full_path = self.repo_root / file_rel_path
            if full_path.exists():
                findings.append(
                    AuditFinding(
                        check_id="config.ssot.deprecated-file",
                        severity=AuditSeverity.ERROR,
                        message=f"Deprecated knowledge file exists: '{file_rel_path}'. The database is the SSOT.",
                        file_path=file_rel_path,
                    )
                )
        return findings

    def _check_required_files(self, required_files: set[str]) -> list[AuditFinding]:
        """Verify that all files declared in meta.yaml exist on disk."""
        findings: list[AuditFinding] = []
        for file_rel_path in sorted(required_files):
            full_path = self.repo_root / file_rel_path
            if not full_path.exists():
                findings.append(
                    AuditFinding(
                        check_id="config.meta.missing-file",
                        severity=AuditSeverity.ERROR,
                        message=f"File declared in meta.yaml is missing: '{file_rel_path}'",
                        file_path=file_rel_path,
                    )
                )
        return findings

    def _check_for_orphaned_intent_files(
        self, declared_files: set[str]
    ) -> list[AuditFinding]:
        """Find .intent files not referenced in meta.yaml."""
        findings: list[AuditFinding] = []
        all_known_files = declared_files.union(KNOWN_UNINDEXED_FILES)
        if (self.intent_path / "proposals/README.md").exists():
            all_known_files.add(".intent/proposals/README.md")
        physical_files: set[str] = {
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
                    check_id="config.meta.orphaned-file",
                    severity=AuditSeverity.WARNING,
                    message=f"Orphaned file in .intent/: '{orphan}'. Add to meta.yaml or remove.",
                    file_path=orphan,
                )
            )
        return findings
