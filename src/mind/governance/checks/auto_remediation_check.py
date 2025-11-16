# src/mind/governance/checks/auto_remediation_check.py
"""
Enforces coverage.auto_remediation: AI must auto-remediate coverage gaps.
"""

from __future__ import annotations

from pathlib import Path

from shared.models import AuditFinding, AuditSeverity

from mind.governance.checks.base_check import BaseCheck


# ID: h8i9j0k1-l2m3-4n4o-5p6q-7r8s9t0u1v2w
# ID: 6a68225c-4494-44e7-b036-c481669dc537
class AutoRemediationCheck(BaseCheck):
    policy_rule_ids = ["coverage.auto_remediation"]

    # ID: 9fd8bfd4-9046-456e-b30b-7d5210ad5d35
    def execute(self) -> list[AuditFinding]:
        findings = []

        coverage_file = Path(".coverage")
        if not coverage_file.exists():
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

        # Check if coverage < 95%
        import xml.etree.ElementTree as ET

        report = Path("htmlcov/index.html")
        if report.exists():
            tree = ET.parse(report)
            root = tree.getroot()
            percent = root.find(".//span[@class='pc_cov']").text
            if percent and float(percent.strip("%")) < 95:
                findings.append(
                    AuditFinding(
                        check_id="coverage.auto_remediation",
                        severity=AuditSeverity.ERROR,
                        message=f"Coverage {percent} < 95%. Run `fix coverage`.",
                        file_path="htmlcov/index.html",
                        line_number=1,
                    )
                )

        return findings
