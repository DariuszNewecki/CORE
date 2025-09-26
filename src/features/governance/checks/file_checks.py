# src/features/governance/checks/file_checks.py
"""
Audits file existence and orphan detection for constitutional governance files.
"""
from __future__ import annotations

from typing import List, Set

from features.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity
from shared.utils.constitutional_parser import get_all_constitutional_paths

# Files that are allowed to exist but are not indexed in meta.yaml
KNOWN_UNINDEXED_FILES = {
    ".intent/charter/constitution/approvers.yaml.example",
    ".intent/keys/private.key",
    ".intent/proposals/README.md",
}


# ID: 8d4158b7-1460-4f64-ab33-341f35e8871e
class FileChecks(BaseCheck):
    """Container for file-based constitutional checks."""

    # ID: ce9c74ec-b6d4-478d-88ce-9e5730c0e4e3
    def execute(self) -> List[AuditFinding]:
        """Runs all file-related checks."""
        findings = self._check_required_files()
        findings.extend(self._check_for_orphaned_intent_files())
        return findings

    def _check_required_files(self) -> List[AuditFinding]:
        """Verify that all files declared in meta.yaml exist on disk."""
        findings: List[AuditFinding] = []
        required_files = get_all_constitutional_paths(self.intent_path)

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

    def _check_for_orphaned_intent_files(self) -> List[AuditFinding]:
        """Find .intent files not referenced in meta.yaml."""
        findings: List[AuditFinding] = []
        declared_files = get_all_constitutional_paths(self.intent_path)
        all_known_files = declared_files.union(KNOWN_UNINDEXED_FILES)

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
