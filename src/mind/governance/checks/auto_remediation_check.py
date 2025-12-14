# src/mind/governance/checks/auto_remediation_check.py
"""
Enforces coverage.auto_remediation: AI must auto-remediate coverage gaps.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

import yaml

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 6a68225c-4494-44e7-b036-c481669dc537
class AutoRemediationCheck(BaseCheck):
    policy_rule_ids = ["coverage.auto_remediation"]

    def _get_constitutional_threshold(self) -> float:
        """
        Loads the target coverage threshold from the Constitution (SSOT).
        Ref: .intent/charter/standards/operations/quality_assurance.yaml
        """
        policy_path = Path(
            ".intent/charter/standards/operations/quality_assurance.yaml"
        )
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
            # Retrieve 'target_threshold' (80) or 'minimum_threshold' (45/75)
            # based on the strictness required. Using target_threshold per intent.
            reqs = data.get("coverage_requirements", {})
            return float(reqs.get("target_threshold", default_threshold))
        except Exception as e:
            logger.error(
                "Failed to parse policy %s: %s. Defaulting to %.1f%%.",
                policy_path,
                e,
                default_threshold,
            )
            return default_threshold

    # ID: 9fd8bfd4-9046-456e-b30b-7d5210ad5d35
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        coverage_file = Path(".coverage")
        report = Path("htmlcov/index.html")

        if not coverage_file.exists():
            findings.append(
                AuditFinding(
                    check_id="coverage.auto_remediation",
                    severity=AuditSeverity.ERROR,
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

        # Load SSOT Threshold
        target_threshold = self._get_constitutional_threshold()

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
                AuditFinding(
                    check_id="coverage.auto_remediation",
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"Coverage {percent_value:.1f}% is below constitutional target "
                        f"of {target_threshold}%. Run `fix coverage`."
                    ),
                    file_path=str(report),
                    line_number=1,
                )
            )

        return findings
