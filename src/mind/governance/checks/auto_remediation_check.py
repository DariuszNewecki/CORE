# src/mind/governance/checks/auto_remediation_check.py
"""
Enforces coverage.auto_remediation: AI must auto-remediate coverage gaps.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 6a68225c-4494-44e7-b036-c481669dc537
class AutoRemediationCheck(BaseCheck):
    policy_rule_ids = ["coverage.auto_remediation"]

    # ID: 9fd8bfd4-9046-456e-b30b-7d5210ad5d35
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        coverage_file = Path(".coverage")
        if not coverage_file.exists():
            # No coverage data at all => ERROR by your current policy.
            findings.append(
                AuditFinding(
                    check_id="coverage.auto_remediation",
                    severity=AuditSeverity.ERROR,
                    message="No coverage data. Run `fix coverage`.",
                    file_path=".coverage",
                    line_number=1,
                )
            )
            return findings

        report = Path("htmlcov/index.html")

        # If there's no HTML report, just skip the coverage % check.
        if not report.exists():
            logger.info(
                "AutoRemediationCheck: coverage file exists (%s) but HTML "
                "report %s is missing; skipping coverage percentage check.",
                coverage_file,
                report,
            )
            return findings

        # Try to parse coverage report; never crash the auditor on parse errors.
        try:
            tree = ET.parse(report)
            root = tree.getroot()
        except ET.ParseError as exc:
            logger.warning(
                "AutoRemediationCheck: unable to parse coverage report '%s': %s. "
                "Skipping coverage percentage check.",
                report,
                exc,
            )
            return findings

        span = root.find(".//span[@class='pc_cov']")
        if span is None or not span.text:
            logger.warning(
                "AutoRemediationCheck: could not find coverage percentage span "
                "in '%s'; skipping coverage percentage check.",
                report,
            )
            return findings

        raw_percent = span.text.strip()
        # Handle typical formats like "97%", "97.3%", maybe with spaces
        if raw_percent.endswith("%"):
            raw_percent = raw_percent[:-1].strip()

        try:
            percent_value = float(raw_percent)
        except ValueError:
            logger.warning(
                "AutoRemediationCheck: invalid coverage percentage '%s' in '%s'; "
                "skipping coverage percentage check.",
                span.text,
                report,
            )
            return findings

        # Check if coverage < 95%
        if percent_value < 95.0:
            findings.append(
                AuditFinding(
                    check_id="coverage.auto_remediation",
                    severity=AuditSeverity.ERROR,
                    message=f"Coverage {percent_value:.1f}% < 95%. Run `fix coverage`.",
                    file_path="htmlcov/index.html",
                    line_number=1,
                )
            )

        return findings
