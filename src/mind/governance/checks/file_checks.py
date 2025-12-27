# src/mind/governance/checks/file_checks.py
"""
Audits file existence, orphan detection, and SSOT compliance.
Uses PathResolver to maintain constitutional boundaries.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, ClassVar

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)

# Knowledge files allowed to stay as files (everything else moves to DB)
_ALLOWED_KNOWLEDGE_FILENAMES = {"domain_definitions.yaml", "project_structure.json"}


# ID: 4f12da52-fdba-4de7-86e8-4e9eb7b7d2c1
class DeprecatedKnowledgeEnforcement(EnforcementMethod):
    """Verifies knowledge state has migrated from files to DB SSOT."""

    # ID: 4ab0f03b-dda1-4fdc-bdfb-74b134cd7dd8
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # CLEAN: Ask the PathResolver where knowledge is
        knowledge_dir = settings.paths.knowledge_dir

        if not knowledge_dir.exists():
            return findings

        for p in knowledge_dir.glob("*"):
            if p.is_file() and p.name not in _ALLOWED_KNOWLEDGE_FILENAMES:
                findings.append(
                    self._create_finding(
                        message=(
                            f"Deprecated knowledge file found: '{p.name}'. "
                            "This resource must be stored in the Database (SSOT)."
                        ),
                        file_path=str(p.relative_to(settings.REPO_PATH)),
                    )
                )
        return findings


# ID: 84c541bf-684b-4826-b10a-64122e6d3c9d
class StructuralComplianceEnforcement(EnforcementMethod):
    """Verifies integrity of the .intent/ directory and its Registry."""

    # ID: 46a530fb-7379-4530-be00-eb42054de0d6
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        # 1. Verify the registry path exists via Resolver
        if not settings.paths.registry_path.exists():
            findings.append(
                AuditFinding(
                    check_id="structural_compliance.registry.missing",
                    severity=AuditSeverity.ERROR,
                    message="intent_types.json is missing. The system Map is broken.",
                    file_path=str(
                        settings.paths.registry_path.relative_to(settings.REPO_PATH)
                    ),
                )
            )
            return findings

        # 2. Enforce JSON-only in policies
        # Note: We use the direct intent_root but stay within the restricted boundary
        policies_dir = settings.paths.intent_root / "policies"
        if policies_dir.exists():
            for p in policies_dir.rglob("*"):
                if p.is_file() and p.suffix != ".json":
                    findings.append(
                        self._create_finding(
                            message=f"Non-canonical file format: '{p.name}'. Policies must be JSON.",
                            file_path=str(p.relative_to(settings.REPO_PATH)),
                        )
                    )

        return findings


# ID: df764b63-edfa-4cd4-9d5a-0a57a6745615
class FileChecks(RuleEnforcementCheck):
    """Enforces structural integrity of the modernized directory structure."""

    policy_rule_ids: ClassVar[list[str]] = [
        "db.ssot_for_operational_data",
        "knowledge.database_ssot",
    ]

    # We can now resolve the policy file path dynamically if needed
    policy_file: ClassVar[Path] = Path(".intent/policies/data/governance.json")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        DeprecatedKnowledgeEnforcement(rule_id="db.ssot_for_operational_data"),
        StructuralComplianceEnforcement(
            rule_id="knowledge.database_ssot", severity=AuditSeverity.ERROR
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
