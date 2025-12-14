# src/mind/governance/checks/duplicate_rule_id_check.py

"""
Constitutional check: Duplicate Rule ID Consistency

Verifies that when the same rule ID appears in multiple policy files,
they are intentional cross-references with consistent enforcement levels.
Ref: standard_policy_integrity
"""

from __future__ import annotations

from collections import defaultdict
from typing import Any

import yaml

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: f75d540b-4161-4eb5-a55e-8a7fab791580
class DuplicateRuleIdCheck(BaseCheck):
    """
    Enforces consistency when rule IDs appear in multiple policy files.
    Supports intentional cross-referencing while catching accidental duplicates.
    """

    policy_rule_ids = [
        "policy.duplicate_rule_id_consistency",
        "policy.cross_reference_documented",
    ]

    # ID: 8c8b4ab0-f832-40fd-b851-cc1b8b8669e7
    def execute(self) -> list[AuditFinding]:
        """Check for duplicate rule IDs across ALL charter files."""
        findings = []

        # SCOPE EXPANSION: Scan all of charter (Constitution, Patterns, Standards)
        # Rule IDs are globally unique across the Mind.
        charter_dir = self.context.intent_path / "charter"

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
                    # Principles dict to list of dicts with 'id'
                    for p_id, p_data in content["principles"].items():
                        if isinstance(p_data, dict):
                            # Inject ID if missing or key-based
                            p_data_copy = p_data.copy()
                            if "id" not in p_data_copy:
                                p_data_copy["id"] = p_id
                            # Constitutional principles are implicitly ERROR
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
                            "file": str(
                                policy_file.relative_to(self.context.repo_path)
                            ),
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
                # Format nice error message showing which file has which severity
                details = [
                    f"{loc['file']} ({loc['raw_severity']})" for loc in locations
                ]
                findings.append(
                    AuditFinding(
                        check_id="policy.duplicate_rule_id_consistency",
                        severity=AuditSeverity.ERROR,
                        message=(
                            f"Rule ID '{rule_id}' has conflicting severities across files: "
                            f"{', '.join(details)}"
                        ),
                        file_path=locations[0]["file"],
                    )
                )

            # Check 2: Cross-Reference Documentation
            has_cross_refs = [loc["has_cross_ref"] for loc in locations]
            if not any(has_cross_refs):
                findings.append(
                    AuditFinding(
                        check_id="policy.cross_reference_documented",
                        severity=AuditSeverity.WARNING,
                        message=(
                            f"Rule ID '{rule_id}' is duplicated across {len(locations)} files "
                            "without documented cross-references. "
                            "Add 'cross_references' or 'implementation_detail'."
                        ),
                        file_path=locations[0]["file"],
                        context={
                            "rule_id": rule_id,
                            "locations": [loc["file"] for loc in locations],
                        },
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
            "implementation_detail",
            "governance_statement",
            "see_also",
            "related_rules",
            "depends_on",  # Added for constitutional principles
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
