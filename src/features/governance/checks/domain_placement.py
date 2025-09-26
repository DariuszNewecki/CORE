# src/features/governance/checks/domain_placement.py
"""
A constitutional audit check to ensure capabilities are declared in the
correct domain manifest file.
"""
from __future__ import annotations

from typing import List

from features.governance.audit_context import AuditorContext
from shared.models import AuditFinding, AuditSeverity
from shared.utils.yaml_processor import yaml_processor


# ID: 0cd8ad5a-ed46-4f18-8335-f95b747d6164
class DomainPlacementCheck:
    """
    Validates that capability keys declared in a domain manifest file
    match the domain of that file.
    """

    def __init__(self, context: AuditorContext):
        self.context = context
        self.domains_dir = self.context.mind_path / "knowledge" / "domains"

    # ID: 7eb75aef-6463-450d-8088-e9a64e3d85c8
    def execute(self) -> List[AuditFinding]:
        """
        Runs the check and returns a list of findings for any violations.
        """
        findings = []
        if not self.domains_dir.is_dir():
            return findings

        for domain_file in self.domains_dir.glob("*.yaml"):
            domain_name = domain_file.stem
            manifest_content = yaml_processor.load(domain_file)
            if not manifest_content:
                continue

            capabilities = manifest_content.get("tags", [])
            if not isinstance(capabilities, list):
                continue

            for cap in capabilities:
                if isinstance(cap, dict) and "key" in cap:
                    cap_key = cap["key"]
                    if not cap_key.startswith(f"{domain_name}."):
                        findings.append(
                            AuditFinding(
                                check_id="domain.placement.mismatch",
                                severity=AuditSeverity.ERROR,
                                message=f"Capability '{cap_key}' is misplaced in '{domain_file.name}'. It should be in a '{cap_key.split('.')[0]}.yaml' manifest.",
                                file_path=str(
                                    domain_file.relative_to(self.context.repo_path)
                                ),
                            )
                        )
        return findings
