# src/mind/governance/checks/policy_format_check.py

"""
Policy Format Enforcement Check

Enforces that all policy documents use v2 flat rules format.
Prevents regression to legacy nested formats.

Constitutional Basis:
- All policies migrated to v2 format on 2024-12-28
- Legacy parser code removed for stability
- This check prevents accidental reintroduction of deprecated formats

Ref: .intent/schemas/META/RULES-STRUCTURE.json
"""

from __future__ import annotations

from pathlib import Path
from typing import ClassVar

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)
FORBIDDEN_LEGACY_SECTIONS = {
    "style_rules",
    "agent_rules",
    "safety_rules",
    "capability_rules",
    "refactoring_rules",
    "module_size_limits",
    "file_header_rules",
    "import_structure_rules",
    "symbol_metadata_rules",
    "health_standards",
    "dependency_injection",
    "naming_conventions",
}


# ID: a3d1e1eb-f5df-46ae-83e7-ea51a91c6324
class PolicyFormatCheck(BaseCheck):
    """
    Enforces v2 flat rules format for all policy documents.

    Prevents regression to deprecated nested formats that were migrated
    on 2024-12-28. All policies must use a flat 'rules' array.

    Ref: .intent/schemas/META/RULES-STRUCTURE.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "policy.flat_rules_required",
        "policy.no_legacy_sections",
    ]

    # ID: 70eba7dd-79c9-414e-81b3-1e7973d44553
    def execute(self) -> list[AuditFinding]:
        """
        Scan all policy files and enforce v2 format.

        Returns:
            List of findings for policies using deprecated formats
        """
        findings = []
        policy_files = self._discover_policy_files()
        if not policy_files:
            logger.warning("No policy files found - this is unexpected")
            return findings
        logger.debug("Checking format for %s policy files", len(policy_files))
        for policy_file in policy_files:
            findings.extend(self._check_policy_file(policy_file))
        return findings

    def _discover_policy_files(self) -> list[Path]:
        """
        Discover all policy JSON files in .intent directory.

        Returns:
            List of policy file paths
        """
        policy_files = []
        intent_root = self.repo_root / ".intent"
        if not intent_root.exists():
            logger.warning("Intent directory not found: %s", intent_root)
            return policy_files
        policies_dir = intent_root / "policies"
        if policies_dir.exists():
            policy_files.extend(policies_dir.glob("**/*.json"))
        standards_dir = intent_root / "charter" / "standards"
        if standards_dir.exists():
            policy_files.extend(standards_dir.glob("**/*.json"))
        return sorted(policy_files)

    def _check_policy_file(self, policy_file: Path) -> list[AuditFinding]:
        """
        Check a single policy file for format compliance.

        Args:
            policy_file: Path to policy file

        Returns:
            List of findings for this file
        """
        findings = []
        try:
            import json

            with open(policy_file, encoding="utf-8") as f:
                content = json.load(f)
            if not isinstance(content, dict):
                return findings
            found_legacy = []
            for section in FORBIDDEN_LEGACY_SECTIONS:
                if section in content:
                    found_legacy.append(section)
            if found_legacy:
                findings.append(
                    AuditFinding(
                        check_id="policy.no_legacy_sections",
                        severity=AuditSeverity.ERROR,
                        message=f"Policy uses deprecated legacy format with sections: {', '.join(found_legacy)}",
                        file_path=str(policy_file.relative_to(self.repo_root)),
                        context={
                            "legacy_sections_found": found_legacy,
                            "required_format": "v2 flat rules array",
                            "migration_date": "2024-12-28",
                            "migration_tool": "policy_format_migration.py",
                            "fix": "Remove legacy sections and move rules to flat 'rules' array",
                        },
                    )
                )
            if "rules" not in content:
                findings.append(
                    AuditFinding(
                        check_id="policy.flat_rules_required",
                        severity=AuditSeverity.ERROR,
                        message="Policy missing required 'rules' array",
                        file_path=str(policy_file.relative_to(self.repo_root)),
                        context={
                            "required_format": "v2 flat rules array",
                            "example": '{"rules": [{"id": "...", "statement": "...", "enforcement": "error"}]}',
                            "reference": ".intent/schemas/META/RULES-STRUCTURE.json",
                        },
                    )
                )
            elif not isinstance(content["rules"], list):
                findings.append(
                    AuditFinding(
                        check_id="policy.flat_rules_required",
                        severity=AuditSeverity.ERROR,
                        message=f"Policy 'rules' must be an array, found: {type(content['rules']).__name__}",
                        file_path=str(policy_file.relative_to(self.repo_root)),
                        context={
                            "actual_type": type(content["rules"]).__name__,
                            "required_type": "list/array",
                        },
                    )
                )
        except json.JSONDecodeError as e:
            logger.debug("Skipping %s - JSON parse error: %s", policy_file, e)
        except Exception as e:
            logger.warning("Error checking policy format for %s: %s", policy_file, e)
        return findings
