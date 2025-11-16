# src/mind/governance/checks/file_checks.py
"""
Audits file existence, orphan detection, and SSOT compliance for
constitutional governance files.
"""

from __future__ import annotations

from shared.config import settings
from shared.models import AuditFinding, AuditSeverity
from shared.utils.constitutional_parser import get_all_constitutional_paths

from mind.governance.checks.base_check import BaseCheck

# This maps the legacy file path to the specific constitutional rule it violates.
# This makes the check a direct enforcer of the data_governance policy.
DEPRECATED_KNOWLEDGE_MAP = {
    ".intent/mind/knowledge/cli_registry.yaml": "db.cli_registry_in_db",
    ".intent/mind/knowledge/resource_manifest.yaml": "db.llm_resources_in_db",
    ".intent/mind/knowledge/cognitive_roles.yaml": "db.cognitive_roles_in_db",
}

KNOWN_UNINDEXED_FILES = {
    ".intent/charter/constitution/approvers.yaml.example",
    ".intent/keys/private.key",
}


# ID: 37b5ae2f-c3c2-4db4-9677-f16fd788c908
class FileChecks(BaseCheck):
    """
    Container for file-based constitutional checks, ensuring structural
    integrity and adherence to the Single Source of Truth (SSOT) principle.
    """

    # Explicit Constitutional Linkage:
    # This check directly enforces the data_governance rules for DB as SSOT
    # and contributes to overall structural_compliance from the QA policy.
    policy_rule_ids = [
        "db.cli_registry_in_db",
        "db.llm_resources_in_db",
        "db.cognitive_roles_in_db",
        "structural_compliance",  # For orphan/missing file checks
    ]

    # ID: 56481071-3a0c-437d-ba57-533bc03d9ed6
    def execute(self) -> list[AuditFinding]:
        """Runs all file-related checks."""
        meta_content = settings._meta_config
        required_files = get_all_constitutional_paths(meta_content, self.intent_path)

        findings = self._check_for_deprecated_files()
        findings.extend(self._check_required_files(required_files))
        findings.extend(self._check_for_orphaned_intent_files(required_files))
        return findings

    def _check_for_deprecated_files(self) -> list[AuditFinding]:
        """
        Verify that files constitutionally replaced by the database do not exist,
        creating a finding for each specific rule violation.
        """
        findings: list[AuditFinding] = []
        for file_rel_path, rule_id in DEPRECATED_KNOWLEDGE_MAP.items():
            full_path = self.repo_root / file_rel_path
            if full_path.exists():
                findings.append(
                    AuditFinding(
                        # The check_id is now the exact ID from the constitution.
                        check_id=rule_id,
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Deprecated knowledge file exists: '{file_rel_path}'. "
                            f"Per rule '{rule_id}', the database is the SSOT."
                        ),
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
                        # This check contributes to the broader structural_compliance rule.
                        check_id="structural_compliance.meta.missing_file",
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
                    # This also contributes to the structural_compliance rule.
                    check_id="structural_compliance.meta.orphaned_file",
                    severity=AuditSeverity.WARNING,
                    message=f"Orphaned file in .intent/: '{orphan}'. Add to meta.yaml or remove.",
                    file_path=orphan,
                )
            )
        return findings
