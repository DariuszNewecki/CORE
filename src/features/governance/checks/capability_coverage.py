# src/features/governance/checks/capability_coverage.py
"""
A constitutional audit check to ensure that all capabilities declared in the
project manifest are implemented in the database.
"""
from __future__ import annotations

from typing import List, Set

from features.governance.audit_context import AuditorContext
from shared.models import AuditFinding, AuditSeverity


# ID: 979ce56f-7f3c-40e7-8736-ce219bab6ad8
class CapabilityCoverageCheck:
    """
    Verifies that every capability in the manifest has a corresponding
    implementation entry in the database's symbols table.
    """

    def __init__(self, context: AuditorContext):
        self.context = context

    # ID: e0730fb8-2616-42b2-915b-48f30ff4ac17
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check and returns a list of findings for any violations.
        """
        findings = []

        manifest_path = self.context.mind_path / "project_manifest.yaml"
        if not manifest_path.exists():
            findings.append(
                AuditFinding(
                    check_id="manifest.missing.project_manifest",
                    severity=AuditSeverity.ERROR,
                    message="The project_manifest.yaml file is missing from .intent/mind/.",
                    file_path=str(manifest_path.relative_to(self.context.repo_path)),
                )
            )
            return findings

        manifest_content = self.context._load_yaml(manifest_path)
        declared_capabilities: Set[str] = set(manifest_content.get("capabilities", []))

        # --- THIS IS THE CORRECT LOGIC ---
        # The source of truth for implementation is the database, not code comments.
        implemented_capabilities: Set[str] = {
            s["key"]
            for s in self.context.knowledge_graph.get("symbols", {}).values()
            if s.get("key")  # A symbol has a capability if its 'key' is not null
        }
        # --- END OF CORRECT LOGIC ---

        missing_implementations = declared_capabilities - implemented_capabilities

        for cap_key in sorted(list(missing_implementations)):
            findings.append(
                AuditFinding(
                    check_id="capability.coverage.missing_implementation",
                    severity=AuditSeverity.WARNING,
                    message=f"Capability '{cap_key}' is declared in the manifest but has no implementation linked in the database.",
                    file_path=str(manifest_path.relative_to(self.context.repo_path)),
                )
            )

        return findings
