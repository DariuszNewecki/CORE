# src/mind/governance/checks/duplicate_rule_id_check.py
"""
Constitutional check: Duplicate Rule ID Consistency

Verifies that when the same rule ID appears in multiple policy files,
they are intentional cross-references with consistent enforcement levels.

Ref: .intent/charter/standards/policy_integrity.json
"""

from __future__ import annotations

from collections import defaultdict
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


logger = getLogger(__name__)

POLICY_INTEGRITY = Path(".intent/charter/standards/policy_integrity.json")


# ID: duplicate-rule-id-enforcement
# ID: 11857efe-f45a-47f5-b9a2-1b914adac004
class DuplicateRuleIdEnforcement(EnforcementMethod):
    """
    Enforces consistency when rule IDs appear in multiple policy files.
    Supports intentional cross-referencing while catching accidental duplicates.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 6dda975c-4d81-4468-b0c2-cc21e575c8f0
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        """Check for duplicate rule IDs across ALL charter files."""
        findings = []

        # SCOPE EXPANSION: Scan all of charter (Constitution, Patterns, Standards)
        # Rule IDs are globally unique across the Mind.
        charter_dir = context.intent_path / "charter"

        if not charter_dir.exists():
            return findings

        rule_locations: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for policy_file in charter_dir.rglob("*.yaml"):
            if policy_file.name.startswith("."):
                continue

            try:
                content = yaml.safe_load(policy_file.read_text(encoding="utf-8"))
                if not content or not isinstance(content, dict):
                    continue

                # Support Big Boys Pattern (rules) + Legacy (agent_rules, etc.)
                rules_lists = []

                # 1. Standard v2 Flat Rules
                if "rules" in content and isinstance(content["rules"], list):
                    rules_lists.extend(content["rules"])

                # 2. Constitutional Principles (mapped to rules for ID checking)
                if "principles" in content and isinstance(content["principles"], dict):
                    for p_id, p_data in content["principles"].items():
                        if isinstance(p_data, dict):
                            p_data_copy = p_data.copy()
                            if "id" not in p_data_copy:
                                p_data_copy["id"] = p_id
                            if "enforcement" not in p_data_copy:
                                p_data_copy["enforcement"] = "error"
                            rules_lists.append(p_data_copy)

                # 3. Legacy Formats (Deprecation path)
                for key in ["agent_rules", "safety_rules", "coding_rules"]:
                    if key in content and isinstance(content[key], list):
                        rules_lists.extend(content[key])

                for rule in rules_lists:
                    if not isinstance(rule, dict):
                        continue

                    rule_id = rule.get("id") or rule.get("principle_id")
                    if not rule_id:
                        continue

                    raw_severity = (
                        rule.get("severity") or rule.get("enforcement") or "unknown"
                    )

                    rule_locations[rule_id].append(
                        {
                            "file": str(policy_file.relative_to(context.repo_path)),
                            "severity": self._normalize_severity(raw_severity),
                            "raw_severity": raw_severity,
                            "statement": rule.get("statement", rule.get("title", "")),
                            "has_cross_ref": self._has_cross_reference(rule),
                            "rule": rule,
                        }
                    )

            except Exception as e:
                logger.warning("Failed to parse %s: %s", policy_file, e)
                continue

        # Check for Inconsistencies
        for rule_id, locations in rule_locations.items():
            if len(locations) <= 1:
                continue

            # Check 1: Severity Consistency
            severities = {loc["severity"] for loc in locations}
            if len(severities) > 1:
                details = [
                    f"{loc['file']} ({loc['raw_severity']})" for loc in locations
                ]
                findings.append(
                    self._create_finding(
                        message=(
                            f"Rule ID '{rule_id}' has conflicting severities across files: "
                            f"{', '.join(details)}"
                        ),
                        file_path=locations[0]["file"],
                    )
                )

        return findings

    def _normalize_severity(self, severity: Any) -> str:
        """Normalize severity strings (e.g., warn == warning)."""
        s = str(severity).lower().strip()
        if s == "warning":
            return "warn"
        return s

    def _has_cross_reference(self, rule: dict[str, Any]) -> bool:
        """Check if rule has cross-reference documentation."""
        cross_ref_keys = [
            "cross_references",
            "cross_reference",
            "implementation_detail",
            "governance_statement",
            "see_also",
            "related_rules",
            "depends_on",
        ]

        for key in cross_ref_keys:
            if key in rule:
                return True

        # Check text fields for keywords
        text_fields = [
            rule.get("description", ""),
            rule.get("statement", ""),
            rule.get("rationale", ""),
        ]

        cross_ref_phrases = [
            "see also",
            "defined in",
            "implemented in",
            "specified in",
            "detailed in",
            "refers to",
            "reference",
        ]

        for text in text_fields:
            if isinstance(text, str):
                text_lower = text.lower()
                for phrase in cross_ref_phrases:
                    if phrase in text_lower:
                        return True

        return False


# ID: cross-reference-documented-enforcement
# ID: eefb8002-1186-4aa1-83c4-0541123954b5
class CrossReferenceDocumentedEnforcement(EnforcementMethod):
    """
    Enforces that duplicate rule IDs have documented cross-references.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.WARNING):
        super().__init__(rule_id, severity)

    # ID: 058dc8e9-5537-4238-b08e-ef7cec303c4d
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any]
    ) -> list[AuditFinding]:
        """Check that duplicates have cross-references."""
        findings = []

        charter_dir = context.intent_path / "charter"
        if not charter_dir.exists():
            return findings

        rule_locations: dict[str, list[dict[str, Any]]] = defaultdict(list)

        for policy_file in charter_dir.rglob("*.yaml"):
            if policy_file.name.startswith("."):
                continue

            try:
                content = yaml.safe_load(policy_file.read_text(encoding="utf-8"))
                if not content or not isinstance(content, dict):
                    continue

                rules_lists = []
                if "rules" in content and isinstance(content["rules"], list):
                    rules_lists.extend(content["rules"])

                for rule in rules_lists:
                    if not isinstance(rule, dict):
                        continue

                    rule_id = rule.get("id")
                    if not rule_id:
                        continue

                    rule_locations[rule_id].append(
                        {
                            "file": str(policy_file.relative_to(context.repo_path)),
                            "has_cross_ref": self._has_cross_reference(rule),
                        }
                    )

            except Exception as e:
                logger.warning("Failed to parse %s: %s", policy_file, e)
                continue

        # Check for missing cross-references
        for rule_id, locations in rule_locations.items():
            if len(locations) <= 1:
                continue

            has_cross_refs = [loc["has_cross_ref"] for loc in locations]
            if not any(has_cross_refs):
                findings.append(
                    self._create_finding(
                        message=(
                            f"Rule ID '{rule_id}' is duplicated across {len(locations)} files "
                            "without documented cross-references. "
                            "Add 'cross_reference' or 'implementation_detail'."
                        ),
                        file_path=locations[0]["file"],
                    )
                )

        return findings

    def _has_cross_reference(self, rule: dict[str, Any]) -> bool:
        """Check if rule has cross-reference documentation."""
        cross_ref_keys = [
            "cross_references",
            "cross_reference",
            "implementation_detail",
            "governance_statement",
            "see_also",
            "related_rules",
            "depends_on",
        ]
        return any(key in rule for key in cross_ref_keys)


# ID: 8c8b4ab0-f832-40fd-b851-cc1b8b8669e7
class DuplicateRuleIdCheck(RuleEnforcementCheck):
    """
    Enforces consistency when rule IDs appear in multiple policy files.
    Supports intentional cross-referencing while catching accidental duplicates.

    Ref: .intent/charter/standards/policy_integrity.json
    """

    policy_rule_ids: ClassVar[list[str]] = [
        "policy.duplicate_rule_id_consistency",
        "policy.cross_reference_documented",
    ]

    policy_file: ClassVar[Path] = POLICY_INTEGRITY

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        DuplicateRuleIdEnforcement(rule_id="policy.duplicate_rule_id_consistency"),
        CrossReferenceDocumentedEnforcement(
            rule_id="policy.cross_reference_documented", severity=AuditSeverity.WARNING
        ),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
