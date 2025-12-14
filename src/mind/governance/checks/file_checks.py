# src/mind/governance/checks/file_checks.py
"""
Audits file existence, orphan detection, and SSOT compliance for
constitutional governance files.
Ref: standard_operations_general (Structural Compliance)
Ref: standard_data_governance (DB SSOT)
"""

from __future__ import annotations

from fnmatch import fnmatch

import yaml

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.utils.constitutional_parser import get_all_constitutional_paths


logger = getLogger(__name__)

# Enforces Data Governance: These files are deprecated in favor of DB tables
DEPRECATED_KNOWLEDGE_MAP = {
    ".intent/mind/knowledge/cli_registry.yaml": "db.cli_registry_in_db",
    ".intent/mind/knowledge/resource_manifest.yaml": "db.llm_resources_in_db",
    ".intent/mind/knowledge/cognitive_roles.yaml": "db.cognitive_roles_in_db",
}

# Per GLOBAL-DOCUMENT-META-SCHEMA.yaml scope.excludes
CONSTITUTIONAL_EXCLUSIONS = [
    ".intent/keys/**",
    ".intent/mind_export/**",
    ".intent/proposals/**",
    # Additional operational exclusions
    ".intent/mind/prompts/*.prompt",  # Prompts are assets, not policies
    ".intent/charter/schemas/**/*.json",  # Schemas are validation templates
    ".intent/reports/**",  # Runtime artifacts
]


# ID: 37b5ae2f-c3c2-4db4-9677-f16fd788c908
class FileChecks(BaseCheck):
    """
    Ensures structural integrity of the .intent/ directory.
    1. Verifies no legacy files exist (DB SSOT).
    2. Verifies all files in meta.yaml exist.
    3. Verifies no orphaned files exist (untracked intent).
    """

    policy_rule_ids = [
        "db.cli_registry_in_db",
        "db.llm_resources_in_db",
        "db.cognitive_roles_in_db",
        "structural_compliance",
    ]

    # ID: 56481071-3a0c-437d-ba57-533bc03d9ed6
    def execute(self) -> list[AuditFinding]:
        findings = []

        # 1. Load Meta Manifest (Source of Truth for File Structure)
        meta_path = self.intent_path / "meta.yaml"
        if not meta_path.exists():
            return [
                AuditFinding(
                    check_id="structural_compliance.meta.missing",
                    severity=AuditSeverity.CRITICAL,
                    message=".intent/meta.yaml is missing. Governance structure is broken.",
                    file_path=".intent/meta.yaml",
                )
            ]

        try:
            meta_content = yaml.safe_load(meta_path.read_text(encoding="utf-8"))
            required_files = get_all_constitutional_paths(
                meta_content, self.intent_path
            )
        except Exception as e:
            logger.error("Failed to parse meta.yaml: %s", e)
            return []

        # 2. Run Checks
        findings.extend(self._check_for_deprecated_files())
        findings.extend(self._check_required_files(required_files))
        findings.extend(self._check_for_orphaned_intent_files(required_files))

        return findings

    def _check_for_deprecated_files(self) -> list[AuditFinding]:
        """Verify that files constitutionally replaced by the database do not exist."""
        findings = []
        for file_rel_path, rule_id in DEPRECATED_KNOWLEDGE_MAP.items():
            full_path = self.repo_root / file_rel_path
            if full_path.exists():
                findings.append(
                    AuditFinding(
                        check_id=rule_id,
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Deprecated file exists: '{file_rel_path}'. "
                            "This data has moved to the Database (SSOT)."
                        ),
                        file_path=file_rel_path,
                    )
                )
        return findings

    def _check_required_files(self, required_files: set[str]) -> list[AuditFinding]:
        """Verify that all files declared in meta.yaml exist on disk."""
        findings = []
        for file_rel_path in sorted(required_files):
            full_path = self.repo_root / file_rel_path
            if not full_path.exists():
                findings.append(
                    AuditFinding(
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
        """
        Find .intent files not referenced in meta.yaml.
        Respects exclusions defined in GLOBAL-DOCUMENT-META-SCHEMA.
        """
        findings = []

        # Get all physical files in .intent/
        physical_files = {
            str(p.relative_to(self.repo_root)).replace("\\", "/")
            for p in self.intent_path.rglob("*")
            if p.is_file()
        }

        # Add meta.yaml itself to known files
        all_known_files = declared_files.union({".intent/meta.yaml"})

        orphaned_candidates = sorted(physical_files - all_known_files)

        for orphan in orphaned_candidates:
            # Check against exclusion patterns (glob matching)
            is_excluded = False
            for pattern in CONSTITUTIONAL_EXCLUSIONS:
                # patterns in list are relative to repo root, e.g. .intent/keys/**
                # fnmatch handles globbing
                if fnmatch(orphan, pattern):
                    is_excluded = True
                    break

            if is_excluded:
                continue

            findings.append(
                AuditFinding(
                    check_id="structural_compliance.meta.orphaned_file",
                    severity=AuditSeverity.WARNING,
                    message=(
                        f"Orphaned file in .intent/: '{orphan}'. "
                        "Governance files must be registered in meta.yaml."
                    ),
                    file_path=orphan,
                )
            )

        return findings
