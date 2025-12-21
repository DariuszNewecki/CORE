# src/mind/governance/checks/file_checks.py
"""
Audits file existence, orphan detection, and SSOT compliance for
constitutional governance files.

Ref: .intent/charter/standards/data/governance.json
"""

from __future__ import annotations

from fnmatch import fnmatch
from pathlib import Path
from typing import Any, ClassVar

import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity
from shared.utils.constitutional_parser import get_all_constitutional_paths


logger = getLogger(__name__)

GOVERNANCE_POLICY = Path(".intent/charter/standards/data/governance.json")

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

# Knowledge YAMLs under `.intent/mind/knowledge/` that are explicitly allowed.
# Everything else in that folder should be considered deprecated in favor of DB SSOT.
_ALLOWED_KNOWLEDGE_FILENAMES = {
    "domain_definitions.yaml",
}


# ID: deprecated-knowledge-enforcement
# ID: ccd8056b-e7a4-4d51-b11b-ae2d8df73d13
class DeprecatedKnowledgeEnforcement(EnforcementMethod):
    """
    Verifies that knowledge sources that are constitutionally replaced by DB SSOT
    do not exist as YAML files under `.intent/mind/knowledge/`.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: f9d6f696-7bdc-4d79-8238-0d82a1d505b5
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        knowledge_dir = context.intent_path / "mind" / "knowledge"
        if not knowledge_dir.exists():
            return findings

        deprecated: list[str] = []
        for p in knowledge_dir.glob("*.yaml"):
            if p.name in _ALLOWED_KNOWLEDGE_FILENAMES:
                continue
            deprecated.append(str(p.relative_to(context.repo_path)).replace("\\", "/"))

        if not deprecated:
            return findings

        # Emit one finding per file so remediation is clear
        for rel_path in sorted(deprecated):
            findings.append(
                self._create_finding(
                    message=(
                        "Deprecated knowledge file exists under .intent/mind/knowledge/. "
                        "Knowledge registries/resources/roles must be stored in the Database (SSOT), "
                        "not as YAML files."
                    ),
                    file_path=rel_path,
                )
            )
        return findings


# ID: structural-compliance-enforcement
# ID: aa809f76-1c5c-4ea4-b0fb-f8947fb4e5b9
class StructuralComplianceEnforcement(EnforcementMethod):
    """
    Verifies structural integrity of the .intent/ directory:
    1. Verifies all files in meta.yaml exist
    2. Verifies no orphaned files exist (untracked intent)
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 400f700c-e8d0-4cfb-9802-5fed07185bdc
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        meta_path = context.intent_path / "meta.yaml"
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
                meta_content, context.intent_path
            )
        except Exception as e:
            logger.error("Failed to parse meta.yaml: %s", e)
            return findings

        findings.extend(self._check_required_files(context, required_files))
        findings.extend(self._check_for_orphaned_intent_files(context, required_files))
        return findings

    def _check_required_files(
        self, context: AuditorContext, required_files: set[str]
    ) -> list[AuditFinding]:
        """Verify that all files declared in meta.yaml exist on disk."""
        findings = []
        for file_rel_path in sorted(required_files):
            full_path = context.repo_path / file_rel_path
            if not full_path.exists():
                findings.append(
                    self._create_finding(
                        message=f"File declared in meta.yaml is missing: '{file_rel_path}'",
                        file_path=file_rel_path,
                    )
                )
        return findings

    def _check_for_orphaned_intent_files(
        self, context: AuditorContext, declared_files: set[str]
    ) -> list[AuditFinding]:
        """
        Find .intent files not referenced in meta.yaml.
        Respects exclusions defined in GLOBAL-DOCUMENT-META-SCHEMA.
        """
        findings = []

        physical_files = {
            str(p.relative_to(context.repo_path)).replace("\\", "/")
            for p in context.intent_path.rglob("*")
            if p.is_file()
        }

        all_known_files = declared_files.union({".intent/meta.yaml"})
        orphaned_candidates = sorted(physical_files - all_known_files)

        for orphan in orphaned_candidates:
            if any(fnmatch(orphan, pattern) for pattern in CONSTITUTIONAL_EXCLUSIONS):
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


# ID: 37b5ae2f-c3c2-4db4-9677-f16fd788c908
class FileChecks(RuleEnforcementCheck):
    """
    Ensures structural integrity of the .intent/ directory.
    1. Verifies no deprecated knowledge YAMLs exist (DB SSOT).
    2. Verifies all files in meta.yaml exist.
    3. Verifies no orphaned files exist (untracked intent).

    Ref: .intent/charter/standards/data/governance.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "db.cli_registry_in_db",
        "knowledge.database_ssot",
    ]

    policy_file: ClassVar[Path] = GOVERNANCE_POLICY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        DeprecatedKnowledgeEnforcement(rule_id="db.cli_registry_in_db"),
        StructuralComplianceEnforcement(
            rule_id="knowledge.database_ssot", severity=AuditSeverity.ERROR
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
