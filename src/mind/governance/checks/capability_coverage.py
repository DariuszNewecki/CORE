# src/mind/governance/checks/capability_coverage.py
"""
A constitutional audit check to ensure that all capabilities declared in the
project manifest are implemented in the database, enforcing the 'knowledge.database_ssot' rule.
"""

from __future__ import annotations

from shared.models import AuditFinding, AuditSeverity

# Import the BaseCheck to inherit from it
from mind.governance.checks.base_check import BaseCheck


# ID: 979ce56f-7f3c-40e7-8736-ce219bab6ad8
# Inherit from BaseCheck
# ID: 92f0b3ec-48d7-49f0-aace-2c894186a46f
class CapabilityCoverageCheck(BaseCheck):
    """
    Verifies that every capability in the manifest has a corresponding
    implementation entry in the database's symbols table.
    """

    # Fulfills the contract from BaseCheck, linking this check directly
    # to the data_governance policy.
    policy_rule_ids = ["knowledge.database_ssot"]

    # The __init__ method is no longer needed; it is handled by BaseCheck.

    # ID: e0730fb8-2616-42b2-915b-48f30ff4ac17
    def execute(self) -> list[AuditFinding]:
        """
        Runs the check and returns a list of findings for any violations.
        """
        findings: list[AuditFinding] = []

        manifest_path = self.context.mind_path / "project_manifest.yaml"
        if not manifest_path.exists():
            # This is a structural issue, not a direct rule violation from the
            # core policies yet. We can give it a more specific check_id
            # related to overall structural compliance.
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

        manifest_content = self.context._load_yaml(manifest_path)
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
                    # The check_id is now the exact ID from the constitution.
                    check_id="knowledge.database_ssot",
                    # The severity now matches the policy's enforcement level.
                    severity=AuditSeverity.ERROR,
                    message=(
                        f"Violation of 'knowledge.database_ssot': Capability '{cap_key}' "
                        "is declared in the manifest but has no implementation in the database (SSOT)."
                    ),
                    file_path=str(manifest_path.relative_to(self.context.repo_path)),
                )
            )

        return findings
