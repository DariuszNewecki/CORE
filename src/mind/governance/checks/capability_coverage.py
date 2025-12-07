# src/mind/governance/checks/capability_coverage.py
"""
A constitutional audit check to ensure that all capabilities declared in the
project manifest are implemented in the database, enforcing the 'knowledge.database_ssot' rule.
"""

from __future__ import annotations

import yaml

from mind.governance.checks.base_check import BaseCheck
from shared.models import AuditFinding, AuditSeverity


# ID: 92f0b3ec-48d7-49f0-aace-2c894186a46f
class CapabilityCoverageCheck(BaseCheck):
    """
    Verifies that every capability in the manifest has a corresponding
    implementation entry in the database's symbols table.
    """

    policy_rule_ids = ["knowledge.database_ssot"]

    # ID: e0730fb8-2616-42b2-915b-48f30ff4ac17
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check and returns a list of findings for any violations.
        """
        findings: list[AuditFinding] = []

        manifest_path = self.context.mind_path / "project_manifest.yaml"
        if not manifest_path.exists():
            findings.append(
                AuditFinding(
                    check_id="structural_compliance.manifest.missing",
                    severity=AuditSeverity.ERROR,
                    message=(
                        "The project_manifest.yaml file is missing from .intent/mind/."
                    ),
                    file_path=str(manifest_path.relative_to(self.context.repo_path)),
                )
            )
            return findings

        with open(manifest_path, encoding="utf-8") as f:
            manifest_content = yaml.safe_load(f)

        declared_capabilities: set[str] = set(manifest_content.get("capabilities", []))

        # SSOT-correct logic: The database is the source of truth.
        implemented_capabilities: set[str] = {
            s["capability"]
            for s in self.context.knowledge_graph.get("symbols", {}).values()
            if s.get("capability")
        }

        missing_implementations = declared_capabilities - implemented_capabilities

        for cap_key in sorted(missing_implementations):
            findings.append(
                AuditFinding(
                    check_id="knowledge.database_ssot",
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"Violation of 'knowledge.database_ssot': Capability '{cap_key}' "
                        "is declared in the manifest but has no implementation in the database (SSOT)."
                    ),
                    file_path=str(manifest_path.relative_to(self.context.repo_path)),
                )
            )

        return findings
