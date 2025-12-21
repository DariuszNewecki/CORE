# src/mind/governance/checks/auto_remediation_check.py
"""
Enforces qa.remediation.auto_trigger: coverage gaps must trigger auto-remediation.

Ref: .intent/charter/standards/operations/quality_assurance.json
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, ClassVar

import yaml

from mind.governance.audit_context import AuditorContext
from mind.governance.checks.rule_enforcement_check import (
    EnforcementMethod,
    RuleEnforcementCheck,
)
from shared.config import settings
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: coverage-threshold-enforcement
# ID: e4d48407-e9ba-421c-afc2-441cb6f1470e
class CoverageThresholdEnforcement(EnforcementMethod):
    """
    Verifies that test coverage meets the constitutional minimum threshold.
    If coverage drops below minimum, autonomous remediation must be triggered.
    """

    def __init__(self, rule_id: str, severity: AuditSeverity = AuditSeverity.ERROR):
        super().__init__(rule_id, severity)

    # ID: 18690358-ec6c-4377-bc1b-41493d8cfad2
    def verify(
        self, context: AuditorContext, rule_data: dict[str, Any], **kwargs
    ) -> list[AuditFinding]:
        findings = []

        coverage_file = Path(".coverage")
        report = Path("htmlcov/index.html")

        if not coverage_file.exists():
            findings.append(
                self._create_finding(
                    message="No coverage data found. Run `fix coverage`.",
                    file_path=str(coverage_file),
                    line_number=1,
                )
            )
            return findings

        if not report.exists():
            logger.info(
                "Coverage file exists (%s) but HTML report %s is missing; "
                "skipping coverage percentage check.",
                coverage_file,
                report,
            )
            return findings

        # Load SSOT Threshold from policy
        target_threshold = self._get_constitutional_threshold(context)

        try:
            tree = ET.parse(report)
            root = tree.getroot()
        except ET.ParseError as exc:
            logger.warning(
                "Unable to parse coverage report '%s': %s. Skipping check.",
                report,
                exc,
            )
            return findings

        # Attempt to find the standard coverage.py HTML class for percentage
        span = root.find(".//span[@class='pc_cov']")
        if span is None or not span.text:
            logger.warning(
                "Could not find coverage percentage span in '%s'; skipping check.",
                report,
            )
            return findings

        raw_percent = span.text.strip().rstrip("%")

        try:
            percent_value = float(raw_percent)
        except ValueError:
            logger.warning(
                "Invalid coverage percentage '%s' in '%s'; skipping check.",
                span.text,
                report,
            )
            return findings

        # Enforce the Constitutional Threshold (SSOT)
        if percent_value < target_threshold:
            findings.append(
                self._create_finding(
                    message=(
                        f"Coverage {percent_value:.1f}% is below constitutional target "
                        f"of {target_threshold}%. Run `fix coverage`."
                    ),
                    file_path=str(report),
                    line_number=1,
                )
            )

        return findings

    def _get_constitutional_threshold(self, context: AuditorContext) -> float:
        """
        Loads the target coverage threshold from the Constitution (SSOT).
        Ref: .intent/charter/standards/operations/quality_assurance.json
        """
        policy_path = settings.paths.policy("quality_assurance")
        default_threshold = 80.0

        if not policy_path.exists():
            logger.warning(
                "Constitutional policy file not found at %s. Defaulting to %.1f%%.",
                policy_path,
                default_threshold,
            )
            return default_threshold

        try:
            data = yaml.safe_load(policy_path.read_text())
            # Retrieve 'target_threshold' (80) or 'minimum_threshold' (75)
            # Look for qa.coverage.target_threshold rule in rules array
            rules = data.get("rules", [])
            for rule in rules:
                if rule.get("id") == "qa.coverage.target_threshold":
                    # Default to 80% as stated in the rule
                    return 80.0
                elif rule.get("id") == "qa.coverage.minimum_threshold":
                    # Minimum is 75%
                    return 75.0
            return default_threshold
        except Exception as e:
            logger.error(
                "Failed to parse policy %s: %s. Defaulting to %.1f%%.",
                policy_path,
                e,
                default_threshold,
            )
            return default_threshold


# ID: 6a68225c-4494-44e7-b036-c481669dc537
class AutoRemediationCheck(RuleEnforcementCheck):
    """
    Enforces qa.remediation.auto_trigger: coverage gaps must trigger auto-remediation.

    Ref: .intent/charter/standards/operations/quality_assurance.json
    """

    policy_rule_ids: ClassVar[list[str]] = ["qa.remediation.auto_trigger"]

    policy_file: ClassVar = settings.paths.policy("quality_assurance")

    enforcement_methods: ClassVar[list[EnforcementMethod]] = [
        CoverageThresholdEnforcement(rule_id="qa.remediation.auto_trigger"),
    ]

    @property
    def _is_concrete_check(self) -> bool:
        return True
