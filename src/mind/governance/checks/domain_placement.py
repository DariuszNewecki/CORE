# src/mind/governance/checks/domain_placement.py
"""
A constitutional audit check to enforce Architectural Domain Placement.
Verifies that source code resides in valid architectural domains defined in
project_structure.yaml and domain_definitions.yaml.
"""

from __future__ import annotations

import yaml

from mind.governance.checks.base_check import BaseCheck
from shared.logger import getLogger
from shared.models import AuditFinding, AuditSeverity


logger = getLogger(__name__)


# ID: 0cd8ad5a-ed46-4f18-8335-f95b747d6164
class DomainPlacementCheck(BaseCheck):
    """
    Validates that source code files obey the Project Structure contracts.

    1. Features must reside in 'src/features/<valid_domain>/'.
    2. Valid domains are defined in 'domain_definitions.yaml'.
    3. Top-level src directories must match 'architectural_domains' in 'project_structure.yaml'.
    """

    policy_rule_ids = [
        "structural_compliance",
    ]

    # ID: 7eb75aef-6463-450d-8088-e9a64e3d85c8
    def execute(self) -> list[AuditFinding]:
        findings: list[AuditFinding] = []

        # 1. Load Valid Architectural Domains (api, core, features, services)
        # Ref: .intent/mind/knowledge/project_structure.yaml
        struct_path = self.context.mind_path / "knowledge/project_structure.yaml"
        if not struct_path.exists():
            return []  # Can't enforce if definition missing

        try:
            struct_data = yaml.safe_load(struct_path.read_text())
            arch_domains = {
                d["path"]: d["domain"]
                for d in struct_data.get("architectural_domains", [])
            }
        except Exception as e:
            logger.error("Failed to load project_structure.yaml: %s", e)
            return []

        # 2. Load Valid Business Domains (governance, quality, etc.)
        # Ref: .intent/mind/knowledge/domain_definitions.yaml
        biz_def_path = self.context.mind_path / "knowledge/domain_definitions.yaml"
        valid_biz_domains = set()
        if biz_def_path.exists():
            try:
                biz_data = yaml.safe_load(biz_def_path.read_text())
                valid_biz_domains = {
                    d["name"] for d in biz_data.get("capability_domains", [])
                }
            except Exception as e:
                logger.error("Failed to load domain_definitions.yaml: %s", e)

        # 3. Audit Source Tree
        # We assume src/ is the root of the body
        if not self.src_dir.exists():
            return findings

        for item in self.src_dir.iterdir():
            if (
                not item.is_dir()
                or item.name.startswith("__")
                or item.name.startswith(".")
            ):
                continue

            rel_path = f"src/{item.name}"

            # Check 1: Is this a valid top-level architectural domain?
            if rel_path not in arch_domains:
                findings.append(
                    AuditFinding(
                        check_id="structural_compliance.unknown_arch_domain",
                        severity=AuditSeverity.ERROR,
                        message=f"Directory 'src/{item.name}' is not a valid architectural domain.",
                        file_path=str(item.relative_to(self.repo_root)),
                        context={"valid_paths": list(arch_domains.keys())},
                    )
                )
                continue

            # Check 2: If it's 'features', are subdirectories valid business domains?
            if item.name == "features" and valid_biz_domains:
                for feature_dir in item.iterdir():
                    if not feature_dir.is_dir() or feature_dir.name.startswith("__"):
                        continue

                    if feature_dir.name not in valid_biz_domains:
                        findings.append(
                            AuditFinding(
                                check_id="structural_compliance.unknown_business_domain",
                                severity=AuditSeverity.ERROR,
                                message=(
                                    f"Feature '{feature_dir.name}' is not a registered Business Domain. "
                                    "Define it in domain_definitions.yaml first."
                                ),
                                file_path=str(feature_dir.relative_to(self.repo_root)),
                                context={
                                    "valid_domains": sorted(list(valid_biz_domains))
                                },
                            )
                        )

        return findings
